#!/usr/bin/env python3
"""Crimson Ledger playtest report builder.

Reads one game's journal folder (events.jsonl + meta.json) and writes a
one-page interactive HTML report.

  python playtest_report.py <game journal folder> --game 7
         [--findings findings/game-07.json] [--history history.json]
         [--out ../../design/playtest-reports/game-07.html]

The numbers come from the journal. The findings file (what went well, what to
improve, last game's fixes) is written by hand for each game; without it the
report still builds, with those sections empty.
"""
import argparse, collections, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
num = lambda s: float(s.replace(',', ''))


def money(msg, pat):
    m = re.search(pat, msg)
    return num(m.group(1)) if m else 0.0


def build(game_dir, game_no=None, pid=None):
    ev = [json.loads(l) for l in open(os.path.join(game_dir, 'events.jsonl'), encoding='utf-8') if l.strip()]
    meta = json.load(open(os.path.join(game_dir, 'meta.json'), encoding='utf-8'))
    players = meta.get('players') or []
    if not players or not ev:
        return None
    me = next((p for p in players if p['id'] == pid), players[0])
    pid = me['id']
    ev = [e for e in ev if e.get('pid') in (None, pid)]      # one captain's game
    by = collections.defaultdict(list)
    for e in ev:
        by[e.get('type', '')].append(e)
    over = by['game_over'][0]['turn'] if by.get('game_over') else None
    end = over if over is not None else max(e['turn'] for e in ev) + 1
    scored = lambda e: e['turn'] < end          # months 0 .. end-1 count for the score
    S = lambda t: [e for e in by.get(t, []) if scored(e)]

    # ---- month by month
    series = []
    for e in by['turn_begin']:
        f = next((x for x in e.get('firms', []) if x['id'] == pid), None)
        if not f:
            continue
        series.append(dict(t=e['turn'], date=e['date'], worth=round(f.get('worth', 0)), cash=round(f.get('cash', 0)),
                           bank=round(f.get('bank', 0)), debt=round(f.get('debt', 0)), hold=f.get('hold', 0),
                           used=f.get('used', 0), ships=len(f.get('ships', [])), port=f.get('port', ''),
                           rank=f.get('rank', ''), free=e['turn'] > end if over is not None else False))
    if not series:
        return None
    final = next((s for s in series if s['t'] == end), series[-1])
    peak = max((s for s in series if s['t'] <= end), key=lambda s: s['worth'])

    # ---- trades
    trades = []
    for e in by['buy'] + by['sell']:
        m = re.search(r'(Bought|Sold) (\d+) (\w+) (?:from the hold and warehouse )?for \$([\d,]+)', e['msg'])
        k = re.search(r'\[([\d,.]+) each, dealer margin ([\d.]+)%, market ([\d,.]+) -> ([\d,.]+)', e['msg'])
        if not (m and k):
            continue
        trades.append(dict(t=e['turn'], side=e['type'], good=(e.get('a') or {}).get('good') or m.group(3).lower(), qty=int(m.group(2)),
                           total=round(num(m.group(4))), port=e.get('port', ''), unit=num(k.group(1)),
                           m0=num(k.group(3)), m1=num(k.group(4)), free=not scored(e)))
    trades.sort(key=lambda x: x['t'])
    st = [x for x in trades if not x['free']]
    cargo = collections.OrderedDict()
    for x in st:
        c = cargo.setdefault(x['good'], dict(good=x['good'], bought=0, sold=0, qb=0, qs=0, nb=0, ns=0))
        if x['side'] == 'buy':
            c['bought'] += x['total']; c['qb'] += x['qty']; c['nb'] += 1
        else:
            c['sold'] += x['total']; c['qs'] += x['qty']; c['ns'] += 1
    cargo = sorted(cargo.values(), key=lambda c: c['bought'] - c['sold'])
    for c in cargo:
        c['net'] = c['sold'] - c['bought']
        c['avg_buy'] = round(c['bought'] / c['qb']) if c['qb'] else 0
        c['avg_sell'] = round(c['sold'] / c['qs']) if c['qs'] else 0
    start_year = int(series[0]['date'].split()[-1]) if series else 1860
    yr = lambda t: start_year + t // 12
    years = collections.OrderedDict()
    for x in st:
        y = years.setdefault(yr(x['t']), dict(year=yr(x['t']), bought=0, sold=0, interest=0))
        y['bought' if x['side'] == 'buy' else 'sold'] += x['total']
    interest = 0
    flat = 0
    for e in S('interest'):
        if not isinstance(e.get('bank'), list):
            continue
        d = e['bank'][1] - e['bank'][0]
        interest += d
        flat += e['bank'][0] * 0.01
        years.setdefault(yr(e['turn']), dict(year=yr(e['turn']), bought=0, sold=0, interest=0))['interest'] += d
    years = [dict(y, net=y['sold'] - y['bought'], interest=round(y['interest'])) for y in years.values()]
    big_sells = [x for x in st if x['side'] == 'sell' and x['total'] > 1e6]
    big_buys = [x for x in st if x['side'] == 'buy' and x['total'] > 1e6]

    # ---- money out
    tax = sum((e.get('tax') or 0) for e in S('customs_declare'))
    fines = sum((e.get('fine') or 0) for e in S('customs_declare')) + sum(money(e['msg'], r'fined \$([\d,]+)') for e in S('seized'))
    dues = sum(e.get('total', 0) for e in S('dues'))
    dues_parts = collections.Counter()
    for e in S('dues'):
        for k, v in re.findall(r'(\w+) (-?\d+)', e['msg'][e['msg'].find('('):]):
            dues_parts[k] += int(v)
    protection = [dict(t=e['turn'], paid=round(money(e['msg'], r'Paid \$([\d,]+)'))) for e in S('protection') if 'Paid $' in e['msg']]
    gifts = [dict(t=e['turn'], port=e.get('port', ''), amount=e['a'].get('amount', 0), gain=money(e['msg'], r'standing \+([\d.]+)')) for e in S('gift') if isinstance(e.get('a'), dict)]
    robbed = [dict(t=e['turn'], lost=e.get('lost', 0)) for e in S('robbed')]
    wages = sum(e.get('amount', 0) for e in S('upkeep'))
    idle = sum(e.get('idle', 0) for e in S('idle_wages'))
    yearly = sum(e.get('amount', 0) for e in S('yearly_upkeep'))
    rent = sum(e.get('amount', 0) for e in S('wh_rent'))
    repairs = sum(money(e['msg'], r'for \$([\d,]+)') for e in S('repair'))
    delta = lambda e: (lambda m: num(m.group(1)) - num(m.group(2)) if m else 0)(re.search(r'Silver \$([\d,]+) -> \$([\d,]+)', e['msg']))
    ships_cost = sum(delta(e) for e in S('buy_ship'))
    guns_cost = sum(delta(e) for t in ('buy_cannon', 'fill_cannons', 'buy_gun') for e in S(t))
    estate = sum(delta(e) for e in S('estate') if 'Silver' in e['msg'])
    loan_int = sum(e['debt'][1] - e['debt'][0] for e in S('interest') if isinstance(e.get('debt'), list) and e['debt'][1] > e['debt'][0])
    legend_silver = sum(-delta(e) for e in S('legend') if 'Silver' in e['msg'])
    out = [dict(k='Gifts to Mayors', v=sum(g['amount'] for g in gifts)),
           dict(k='Port Authority tax', v=tax),
           dict(k="Li Yue's protection", v=sum(p['paid'] for p in protection)),
           dict(k='Harbour dues', v=dues),
           dict(k='Robbed ashore', v=sum(r['lost'] for r in robbed)),
           dict(k='Great house (bought)', v=estate),
           dict(k='Crew wages', v=wages),
           dict(k='Ships and cannons', v=ships_cost + guns_cost),
           dict(k='Yearly upkeep', v=yearly),
           dict(k='Repairs', v=repairs),
           dict(k='Fines', v=fines),
           dict(k='Warehouse rent', v=rent),
           dict(k='Loan interest', v=loan_int)]
    out = sorted([dict(k=o['k'], v=round(o['v'])) for o in out if o['v'] > 0], key=lambda o: -o['v'])

    # ---- perils
    results = [e['msg'].split(': ', 1)[-1].split(' against')[0] for e in by['battle_result']]
    battles = []
    asks = [e.get('price') for e in by['parley_refused']]
    for i, e in enumerate(by['battle']):
        m = re.search(r'attacked by (\d+) (.+?):', e['msg'])
        if not m:
            continue
        kind = 'Li Yue war fleet' if 'Li Yue' in m.group(2) else ('small band' if 'little band' in m.group(2) else 'raiders')
        battles.append(dict(t=e['turn'], n=int(m.group(1)), kind=kind,
                            ask=asks[i] if i < len(asks) else None,
                            result=results[i] if i < len(results) else '?', free=not scored(e)))
    res_name = {'won': 'Sank them all', 'broke_off': 'They broke off', 'away': 'Outran them', 'paid': 'Paid to pass'}
    for b in battles:
        b['result'] = res_name.get(b['result'], b['result'])
    storms = []
    for e in by['storm_report']:
        m = e['msg']
        storms.append(dict(t=e['turn'], band=e.get('band', 'rough'), hull=e.get('hull_lost', 0), cargo=sum((e.get('cargo') or {}).values()),
                           cannons=e.get('cannons', 0), landed=(e.get('landing') or {}).get('port'),
                           yard=(e.get('landing') or {}).get('yard'), free=not scored(e)))
    storm_and_fight = sorted(set(s['t'] for s in storms) & set(b['t'] for b in battles))
    lost = [dict(t=e['turn'], name=e.get('name', ''), why=e['msg'].split(': ')[-1]) for e in by['ship_lost']]
    choices = collections.Counter((e.get('a') or {}).get('choice') or 'declared' for e in S('customs_declare'))
    outcomes = collections.Counter(e.get('outcome', '?') for e in S('customs_roll'))
    nothing = [dict(t=e['turn'], port=e.get('port', ''), value=e.get('value', 0)) for e in by['customs_declare'] if (e.get('a') or {}).get('choice') == 'nothing']
    seized = [dict(t=e['turn'], msg=e['msg'].split(': ', 1)[-1]) for e in by['seized']]
    con = by['contract_offered']
    fees = sorted((e.get('contract') or {}).get('fee', 0) for e in con)
    taken = sum(len(by[t]) for t in by if t.startswith('contract_') and t != 'contract_offered')
    marks = []
    for e in by['promotion']:
        marks.append(dict(t=e['turn'], k='rank', label=e.get('rank', 'Promotion')))
    for s in storms:
        if s['band'] != 'rough' and not s['free']:
            marks.append(dict(t=s['t'], k='storm', label=s['band'].capitalize() + ' storm'))
    for b in battles:
        marks.append(dict(t=b['t'], k='fight', label='%d %s: %s' % (b['n'], b['kind'], b['result'].lower())))
    for r in robbed:
        marks.append(dict(t=r['t'], k='robbed', label='Robbed of $%.1fM' % (r['lost'] / 1e6)))
    for e in by['chapter']:
        marks.append(dict(t=e['turn'], k='legend', label='Legend: ' + str(e.get('chapter', ''))))
    for e in by['estate']:
        if 'built' in e['msg']:
            marks.append(dict(t=e['turn'], k='house', label=e['msg'].split('built ')[1].split(' for')[0]))
    ts = [e['t'] for e in ev if 't' in e and (over is None or e['n'] <= by['game_over'][0]['n'])]
    active = sum(b - a for a, b in zip(ts, ts[1:]) if b - a < 300000) / 60000
    standing = {}
    for e in by['standing']:
        m = re.search(r'now ([\d.]+)', e['msg'])
        if m and e.get('port'):
            standing[e['port']] = float(m.group(1))
    seat = (by.get('seat_new') or [{}])[0]
    top = sorted(e['turn'] for e in by['promotion'])
    return dict(
        meta=dict(id=meta['id'], game=game_no, years=meta.get('years'), months=end, house=me.get('firm', ''),
                  captain=me.get('name', ''), pid=pid, started=meta.get('started'), start_port=seat.get('start_port'), finished=over is not None,
                  real_start=ev[0].get('at', '')[:16], real_end=ev[-1].get('at', '')[:16], sessions=len(meta.get('sessions', [])),
                  events=len(ev), active_min=round(active), free_months=max(0, series[-1]['t'] - end) if over is not None else 0,
                  final=final['worth'], rank=final['rank'], peak=peak['worth'], peak_t=peak['t'],
                  top_rank_t=top[-1] if top else None, bank_end=final['bank'], cash_end=final['cash']),
        series=series, marks=marks, cargo=cargo, years=years, trades=trades, out=out,
        totals=dict(bought=sum(c['bought'] for c in cargo), sold=sum(c['sold'] for c in cargo), interest=round(interest),
                    interest_flat=round(flat), legend=round(legend_silver), wages=round(wages), idle=round(idle),
                    sells=len(big_sells), sells_thin=sum(1 for x in big_sells if x['unit'] < 0.9 * x['m1']),
                    buys=len(big_buys), buy_lift=round(sum(x['m1'] / x['m0'] for x in big_buys) / max(1, len(big_buys)), 2),
                    dues_profit=dues_parts.get('profit', 0), dues_bank=dues_parts.get('bank', 0)),
        perils=dict(battles=battles, storms=storms, lost=lost, robbed=robbed, protection=protection, seized=seized,
                    storm_rolls=len(S('storm')), pirate_rolls=len(S('pirates')), storm_and_fight=storm_and_fight,
                    robbery_rolls=len(S('robbery')), jailed=sum(len(by[t]) for t in by if t.startswith('jail') and t != 'jail_contraband')),
        customs=dict(choices=dict(choices), outcomes=dict(outcomes), nothing=nothing, visits=len(S('customs_open')),
                     home=sum(1 for e in S('customs_open') if e.get('rate') == 0)),
        contracts=dict(offered=len(con), taken=taken, fee_median=fees[len(fees) // 2] if fees else 0, fee_max=fees[-1] if fees else 0),
        gifts=gifts, standing=standing,
        ports=collections.Counter(e.get('port', '') for e in S('arrived')).most_common(),
        runs=collections.Counter(e.get('good', '') for e in S('run')).most_common(),
        legends=[e['msg'].split(': ', 1)[-1] for e in by['choice']],
    )


def render(data, template):
    """Drop a game's numbers into the page."""
    blob = json.dumps(data, separators=(',', ':')).replace('</', '<\\/')
    return template.replace('/*__DATA__*/null', blob).replace('__GAME__', str(data['meta'].get('game') or ''))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('game_dir')
    ap.add_argument('--game', type=int)
    ap.add_argument('--findings')
    ap.add_argument('--history', default=os.path.join(HERE, 'history.json'))
    ap.add_argument('--template', default=os.path.join(HERE, 'report_template.html'))
    ap.add_argument('--out')
    ap.add_argument('--json', help='also write the numbers to this file')
    a = ap.parse_args()
    data = build(a.game_dir, a.game)
    if data is None:
        sys.exit('That journal has no players or no months to report on.')
    data['findings'] = json.load(open(a.findings, encoding='utf-8')) if a.findings and os.path.exists(a.findings) else {}
    data['history'] = json.load(open(a.history, encoding='utf-8')) if os.path.exists(a.history) else []
    if a.json:
        json.dump(data, open(a.json, 'w', encoding='utf-8'), indent=1)
    out = a.out or os.path.join(HERE, 'game-%s.html' % (a.game or data['meta']['id']))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'w', encoding='utf-8').write(render(data, open(a.template, encoding='utf-8').read()))
    m = data['meta']
    print('%s: %s months, final $%s, %s. Wrote %s' % (m['id'], m['months'], format(m['final'], ','), m['rank'], out))


if __name__ == '__main__':
    main()
