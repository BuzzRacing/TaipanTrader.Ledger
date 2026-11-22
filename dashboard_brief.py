"""A deterministic observation from the same visibility-limited facts as the dashboard."""
import hashlib
import json

import engine

PERSONAS = {'gamemaster', 'narrator', 'bookmaker', 'taxlady', 'mayor', 'bookkeeper',
            'bosun', 'pirate', 'comprador', 'banker', 'lender'}


def build(feed, snapshot, text=None, goods=None):
    if snapshot.get('phase') in ('lobby', 'ended') or not feed.get('houses'):
        return None
    text = engine.TEXT if text is None else text
    goods = engine.GOODS if goods is None else goods
    candidates = []

    def add(priority, kind, fields, page, **target):
        candidates.append((priority, kind, fields, dict(page=page, **target)))

    for region, level in sorted((snapshot.get('weather') or {}).items()):
        if level >= 2:
            add(100 if level >= 3 else 60, 'weather',
                {'region': (engine.REGIONS.get(region) or {}).get('name', region),
                 'weather': text.get('wx.' + str(level), str(level))}, 'lanes', region=region)
    for house in feed['houses']:
        if any(ship.get('crippled') for ship in house.get('hull') or []):
            add(85, 'fleet', {'firm': house['firm']}, 'fleet')

    # Only public hull/weather facts are inspected when rivals are at the table.
    if not feed.get('locked'):
        bans = snapshot.get('bans') or {}
        for event in feed.get('market_effects') or []:
            if event.get('turns', 0) <= 0:
                continue
            port, good = event['port'], event['good']
            fields = {'port': (engine.PORTS.get(port) or {}).get('name', port),
                      'good': (goods.get(good) or {}).get('name', good),
                      'months': event['turns'], 'mult': '×{:g}'.format(event['mult'])}
            if good in bans.get(port, []):
                add(90, 'ban', fields, 'markets', port=port, good=good)
            elif event['sort'] == 'boom':
                kind = 'expiring' if event['turns'] == 1 else 'boom'
                add(80 if kind == 'expiring' else 65, kind, fields, 'markets', port=port, good=good)
        best = None
        for good in sorted(goods):
            quotes = [(port, row['prices'][good]) for port, row in (feed.get('ports') or {}).items()
                      if good in (row.get('prices') or {}) and good not in bans.get(port, [])
                      and row['prices'][good] > 0]
            if len(quotes) < 2:
                continue
            low, high = min(quotes, key=lambda x: x[1]), max(quotes, key=lambda x: x[1])
            ratio = high[1] / low[1] - 1
            if ratio >= .25 and (best is None or ratio > best[0]):
                best = ratio, good, low, high
        if best:
            _, good, low, high = best
            currency = engine.CFG['brand'].get('currency', '')
            money = lambda amount: currency + '{:,.0f}'.format(amount)
            add(40, 'spread', {'good': goods[good]['name'], 'origin': engine.PORTS[low[0]]['name'],
                              'port': engine.PORTS[high[0]]['name'], 'low': money(low[1]),
                              'high': money(high[1]), 'gap': money(high[1] - low[1])},
                'markets', port=high[0], good=good)
    if not candidates:
        return None
    _, kind, fields, target = max(candidates, key=lambda row: row[0])
    identity = [feed.get('game_id'), feed.get('turn'), kind, target, fields.get('firm'), fields.get('weather')]
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:20]
    line = lambda suffix: text['dash.whisper.' + kind + '.' + suffix].format_map(fields)
    return {'id': key, 'kind': kind, 'title': line('title'), 'text': line('text'),
            'speech': line('speech'), 'target': target,
            'mood': 'concerned' if kind in ('weather', 'fleet', 'ban') else 'sly'}


def voice_reply(brief, persona, part, planner, text):
    if persona not in PERSONAS:
        raise ValueError('Unknown dashboard persona')
    if part not in ('teaser', 'detail'):
        raise ValueError('Unknown dashboard speech part')
    if not brief:
        return {'ok': True, 'brief': None, 'clip': None}
    key = 'dash.whisper.teaser.' + (persona if persona in ('gamemaster', 'narrator', 'bookmaker') else 'other')
    spoken = text[key] if part == 'teaser' else brief['speech']
    return {'ok': True, 'brief': brief, 'clip': planner._clip(spoken, persona) if planner.ready() else None}
