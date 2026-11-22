"use strict";

class TableDirector {
  constructor(show, clock = () => Date.now()) {
    this.show = show; this.clock = clock; this.reset(null);
  }
  reset(game) {
    this.game = game; this.cursor = null; this.queue = []; this.current = null; this.group = null;
    this.seen = new Set(); this.news = new Set(); this.last = null; this.until = 0;
    this.paused = false; this.linger = false; this.serial = 0; this.travel = null;
  }
  enqueue(key, beats, priority = 2, category = '') {
    if (!beats.length || this.seen.has(key)) return;
    this.seen.add(key);
    if (this.seen.size > 2000) this.seen.delete(this.seen.values().next().value);
    const created = this.clock();
    const scenes = beats.map((b, i) => ({ ...b, key: key + ':' + i, sequence: key, beatIndex: i, beatCount: beats.length,
      priority, created, duration: b.duration || Math.min(10000, Math.max(3400, 1600 + (b.text || '').length * 40)) }));
    if (category.startsWith('round:')) this.queue = this.queue.filter(g => g.category !== category);
    if (priority >= 8 && this.group && this.group.priority < 6) {
      this.group.scenes = []; this.until = 0; this.linger = false;
      this.queue = this.queue.filter(g => g.priority >= 6);
    }
    this.queue.push({ key, scenes, priority, category, created, serial: ++this.serial });
    // Core story sequences keep their chronology; bulletins and routine receipts wait for the stage.
    this.queue.sort((a, b) => a.priority >= 6 && b.priority >= 6 ? a.serial - b.serial : b.priority - a.priority || a.serial - b.serial);
    if (this.queue.length > 20) this.queue = this.queue.filter((g, i) => g.priority >= 6 || i < 12);
  }
  host(key, base, line, mood = 'host') {
    return { ...base, kind: 'host', hostKey: key, who: 'gamemaster', mood,
      text: line?.text || '', clips: line?.clip ? [line.clip] : [], hostLine: line };
  }
  customs(report, base, clips = [], text = '', bridge = null) {
    const root = 'customs:' + base.pid + ':' + report.turn + ':' + report.port;
    const common = { ...base, port: report.port, report, who: report.officer || 'officer_' + report.port };
    if (report.status !== 'verdict') {
      this.enqueue(root + ':welcome', [{ ...common, kind: 'customs', text: report.welcome, mood: 'speaking', clips }], 6);
      return;
    }
    const r = report.result || {};
    const bought = (r.lines || []).some(l => l.units && !l.back);
    const mood = r.caught ? 'angry' : 'happy', ruling = r.caught ? 'caught' : bought ? 'buyout' : 'tax';
    this.enqueue(root + ':verdict', [
      { ...common, kind: 'customs', phase: 'verdict', text: report.line || text, mood, ruling, clips },
      { ...common, kind: 'reckoning', source: 'customs', mood, ruling, text: '', duration: 6500 },
      { ...this.host('gm.return', common, bridge, 'sly'), kind: 'return', duration: 5000 }
    ], 7);
  }
  storm(report, base, voice = {}) {
    const root = 'storm:' + base.pid + ':' + report.turn + ':' + report.id;
    const common = { ...base, report, who: 'narrator', mood: 'storm', voice };
    this.enqueue(root, [
      { ...common, kind: 'storm', textKey: report.lines?.open, clips: voice.storm?.open ? [voice.storm.open] : [] },
      { ...common, kind: 'reckoning', source: 'storm', textKey: report.lines?.close,
        clips: voice.storm?.close ? [voice.storm.close] : [], duration: 6500 }
    ], 10);
  }
  battle(report, base, voice, ended = false) {
    const id = ended ? report.id : 'now';
    const frames = report.beat?.frames || [];
    const common = { ...base, report, voice, fightId: id };
    const beats = [];
    frames.forEach((frame, i) => {
      const ours = voice.battle?.[id]?.[i], foe = voice.battle_foe?.[id]?.[i];
      const who = ours?.c || 'bosun';
      beats.push({ ...common, kind: 'battle', frame, beat: i, text: frame.say || '', who, mood: frame.mood || 'speaking',
        side: 'left', peer: frame.foe_by, clips: ours ? [ours] : [] });
      if (frame.foe && frame.foe_by) beats.push({ ...common, kind: 'battle', frame, beat: i, text: frame.foe,
        who: frame.foe_by, mood: frame.foe_mood || 'speaking', side: 'right', peer: who, clips: foe ? [foe] : [] });
    });
    if (!beats.length && !ended) beats.push({ ...common, kind: 'battle', who: 'bosun', mood: 'speaking', text: report.tell || '' });
    if (ended) beats.push({ ...common, kind: 'reckoning', source: 'battle', who: 'bosun',
      mood: report.outcome === 'won' ? 'happy' : ['wrecked','plundered'].includes(report.outcome) ? 'angry' : 'speaking', duration: 7000 });
    const root = ended ? 'fight:' + id : 'round:' + base.pid + ':' + base.turn + ':' + report.kind + ':' + report.step;
    if (ended) this.queue = this.queue.filter(g => !g.category.startsWith('round:' + base.pid + ':'));
    this.enqueue(root, beats, 9, ended ? '' : 'round:' + base.pid + ':' + report.kind);
  }
  ingest(feed) {
    if (feed.game_id !== this.game) this.reset(feed.game_id);
    const s = feed.state, p = feed.focus, events = feed.events || [];
    if (!s) return;
    const initial = this.cursor === null;
    const base = { pid: p?.id, port: p?.port, turn: s.turn, focus: p, state: s, host: feed.host || {}, voice: feed.voice || {} };
    const top = events.reduce((n, e) => Math.max(n, e.n), 0);
    if (initial) {
      for (const f of p?.fights || []) this.seen.add('fight:' + f.id);
    } else for (const e of events) {
      if (e.n <= this.cursor || (e.at && this.clock() - e.at > 90000)) continue;
      const type = e.type, report = e.report;
      const shot = { ...base, pid: e.pid, turn: e.turn, port: e.port || p?.port, date: e.date,
        state: { ...s, turn: e.turn, date: e.date || s.date },
        focus: e.focus || (p && { ...p, port: e.port || p.port, ships: e.ships || p.ships }), voice: e.voice || {} };
      if (type === 'sailed') {
        this.travel = e;
        shot.focus = { ...shot.focus, port: e.origin };
        shot.passage = e.passage;
        this.enqueue('voyage:' + e.n, [
          { ...this.host('gm.departure', shot, e.bridge, 'sly'), kind: 'departure', port: e.origin, dest: e.dest },
          { ...shot, kind: 'voyage', from: e.origin, port: e.dest, who: 'narrator', mood: 'voyage', sea: e.sea,
            text: e.narration?.text || '', clips: e.narration?.clip ? [e.narration.clip] : [], duration: 6500 }
        ], 7);
      } else if (type === 'arrived') {
        this.enqueue('arrival:' + e.n, [
          { ...this.host('gm.arrival', shot, e.bridge), kind: 'landfall' },
          { ...shot, kind: 'arrival', who: 'mayor', mood: 'happy', text: e.welcome || '', clips: e.clips || [], duration: 6500 }
        ], 7);
      } else if (type === 'customs_open' && report) this.customs(report, shot, e.clips || []);
      else if (type === 'customs_declare' && report) this.customs(report, shot, e.clips || [], e.text, e.bridge);
      else if (type === 'storm_report' && report) this.storm(report, shot, e.voice || {});
      else if (type === 'battle_result' && report) this.battle(report, shot, e.voice || {}, true);
      else if (!['sail','stay','battle','round','storm','legend','won','retreat','broke_off','paid','offcourse'].includes(type)) {
        this.enqueue('event:' + e.n, [{ ...shot, ...e, kind: 'trade', text: e.text,
          mood: ['sell','promotion','promoted'].includes(type) ? 'happy' : 'speaking', duration: 6500 }], ['ship_lost','shipwreck','seized'].includes(type) ? 9 : 2);
      }
    }
    this.cursor = Math.max(this.cursor || 0, top);
    if (p) {
      const outstanding = p.storm || p.battle || p.legend || p.jail?.jail || p.jail?.plea;
      if (p.storm) this.storm(p.storm, base, feed.voice || {});
      if (!initial) for (const f of p.fights || []) this.battle(f, base, feed.voice || {}, true);
      if (!p.storm && p.battle) this.battle(p.battle, base, feed.voice || {});
      if (!outstanding && p.customs) this.customs(p.customs, base, feed.voice?.customs?.filter(Boolean) || [], '', feed.host?.['gm.return']);
      if (!p.storm && !p.battle && p.legend) {
        const l = p.legend, root = 'legend:' + l.id + ':' + l.chapter_id + ':' + l.node + ':' + l.step;
        let respondent = (l.beats || []).find(b => b.side === 'right')?.who;
        const beats = (l.beats || []).map((b,i) => ({ ...base, kind: 'legend', who: b.who || l.teller, peer: b.side === 'right' ? l.teller : respondent,
          side: b.side, report: l, beat: i, text: b.text, clips: feed.voice?.legend?.[i] ? [feed.voice.legend[i]] : [] }));
        this.enqueue(root, beats, 8);
      } else if (!outstanding && p.promotion) this.enqueue('promotion:' + p.promotion.id, [{ ...base, kind: 'promotion', who: 'mayor', mood: 'happy', report: p.promotion }], 6);
      else if (!p.storm && !p.battle && (p.jail?.jail || p.jail?.plea)) {
        const j = p.jail.jail || p.jail.plea, beats = [];
        for (const key of j.fresh ? ['caught','warden'] : ['warden']) {
          const line = feed.voice?.jail?.[key];
          if (line?.text) beats.push({ ...base, kind:'jail', who:line.clip?.c || (key === 'caught' ? j.by || 'mayor' : j.warden),
            report:p.jail, text:line.text, clips:line.clip ? [line.clip] : [] });
        }
        beats.push({ ...base, kind:'reckoning', source:'jail', who:j.warden || 'warden_' + p.port, report:p.jail, duration:6500 });
        this.enqueue('jail:' + s.turn + ':' + p.port + ':' + j.since + ':' + Boolean(j.fresh), beats, 8);
      }
    }
    (s.news || []).slice().reverse().forEach(text => {
      if (!initial && !this.news.has(text)) {
        const clip = s.voice?.news?.[s.news.indexOf(text)];
        this.enqueue('news:' + text, [{ ...base, kind:'news', who:clip?.c || 'crier', text, clips:clip ? [clip] : [] }], 1);
      }
      this.news.add(text);
    });
    if (this.last && this.last.turn !== s.turn) this.enqueue('month:' + s.turn,
      [this.host('gm.month_open.' + s.turn % 3, base, feed.host?.['gm.month_open.' + s.turn % 3])], 3);
    this.last = { turn:s.turn, port:p?.port, phase:s.phase };
    this.tick();
  }
  tick() {
    if (this.paused || this.linger) return;
    if (this.current && this.until > 0) {
      if (this.canAdvance ? !this.canAdvance(this.current, this.until) : this.clock() < this.until) return;
    }
    if (!this.group?.scenes.length) {
      this.queue = this.queue.filter(g => g.priority >= 6 || this.clock() - g.created < 45000);
      this.group = this.queue.shift() || null;
    }
    if (!this.group) {
      if (this.current) { this.current = null; this.until = 0; this.show(null); }
      return;
    }
    this.current = this.group.scenes.shift();
    this.current.startedAt = this.clock();
    this.until = this.clock() + this.current.duration;
    this.show(this.current);
  }
  skip() { this.linger = false; this.until = 0; this.tick(); }
  board() { this.queue = []; this.group = null; this.current = null; this.until = 0; this.linger = false; this.show(null); }
  pause() {
    this.paused = !this.paused;
    if (this.paused) this.pausedAt = this.clock();
    else {
      const elapsed = this.clock() - this.pausedAt;
      this.until += elapsed;
      if (this.current) this.current.startedAt += elapsed;
      this.tick();
    }
    return this.paused;
  }
}
if (typeof module !== "undefined") module.exports = TableDirector;
