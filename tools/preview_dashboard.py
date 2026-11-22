"""Read-only dashboard preview with disposable sample standings and the configured art catalog."""
import argparse
import copy
import io
import math
import struct
import sys
import wave
import json
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlparse, parse_qs
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dashboard_brief
import engine
import strings
import voicefloor

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gallery', default='http://192.168.1.69:8765')
    parser.add_argument('--port', type=int, default=18887)
    parser.add_argument('--test-audio', action='store_true', help='Use a quiet test tone instead of paid cast synthesis')
    args = parser.parse_args()
    with urlopen(args.gallery + '/api/info?family=1', timeout=15) as r:
        info = json.load(r)
    info['voice']['enabled'] = args.test_audio
    info['data']['text'].update({k:v for k,v in strings.EN.items() if k.startswith('dash.whisper.')})
    info['data']['text'].update({k:v for k,v in strings.FAMILY.items() if k.startswith('dash.whisper.')})
    engine.PORTS.update(info['data']['ports'])
    engine.REGIONS.update(info['data']['regions'])
    engine.CFG['brand'] = info['data']['brand']
    ports = list(info['data']['ports'])
    goods = list(info['data']['goods'])
    houses = []
    for i, firm in enumerate(['Jade Dragon', 'The Golden Fan', 'East India House', 'Black Orchid']):
        months = [{'turn':t, 'date':f'Month {t+1}', 'worth':int((i+1)*18000+(t+1)*(8000-i*900)+(t%3)*4000)} for t in range(12)]
        houses.append(dict(id=f'p{i}', firm=firm, name=['Anthony','Isabel','Evelyn','Roxana'][i], color=i,
            port=ports[i % len(ports)], worth=months[-1]['worth'], months=months,
            hull=[{'hull':.94-i*.16,'crippled':i==3}], lanes=[], legs=[]))
    feed = dict(ok=True, game_id='dashboard-preview', level='open', locked=False, date='December 1860', turn=11,
        houses=houses, ghost=None, deals=[], lane_profit={}, tape=[],
        ports={p:{'prices':{g:(j+1)*42+(i+1)*17 for j,g in enumerate(goods)},'base':{g:(j+1)*48+32 for j,g in enumerate(goods)}} for i,p in enumerate(ports)},
        market_effects=[dict(port=ports[0],good=goods[0],sort='boom',turns=2,mult=2.4),dict(port=ports[2],good=goods[1],sort='crash',turns=1,mult=.4)],
        booms=[dict(port=ports[0],good=goods[0],sort='boom',date='December 1860',turn=11,turns=2,mult=2.4)])
    state = dict(cfg=info['cfg'], game_id=feed['game_id'], phase='port', date=feed['date'], years=5, turns_left=48,
        players=[dict(h, present=True, ships=1, portrait='',crest='') for h in houses], sea=[], crackdown=[ports[2]], bans={ports[2]:[goods[1]]},
        weather={r:i%len(info['data']['weather']) for i,r in enumerate(info['data']['regions'])})
    tone = io.BytesIO()
    with wave.open(tone, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
        wav.writeframes(b''.join(struct.pack('<h', int(500*math.sin(2*math.pi*330*i/16000))) for i in range(32000)))
    class PreviewVoice:
        def ready(self): return args.test_audio
        def _clip(self, text, cid): return {'c':cid,'u':'/preview-voice.wav'}
    def fixture(referer):
        query = parse_qs(urlparse(referer).query)
        out, snapshot = copy.deepcopy(feed), copy.deepcopy(state)
        if query.get('mode') == ['solo']:
            out['houses'] = out['houses'][:1]
            out['ghost'] = dict(kind='par',date='',curve=[int(m['worth']*.9) for m in houses[0]['months']],final=int(houses[0]['worth']*.9))
            snapshot['players'] = snapshot['players'][:1]
        sample = query.get('notice',[''])[0]
        if sample in ('boom','quiet','spread'):
            snapshot['weather'] = {k:0 for k in snapshot['weather']}
            snapshot['bans'] = {}
            for house in out['houses']:
                for ship in house['hull']: ship['crippled'] = False
            if sample == 'boom':
                out['market_effects'] = [dict(port=ports[0],good=goods[0],sort='boom',turns=1,mult=2.4)]
            else:
                out['market_effects'] = []
            if sample == 'quiet':
                for row in out['ports'].values(): row['prices'] = {g:100 for g in goods}
        if query.get('mode') == ['public']:
            out.update(locked=True,level='public')
            for k in ['ports','deals','lane_profit','booms','market_effects']: out.pop(k,None)
        out['brief'] = dashboard_brief.build(out,snapshot,info['data']['text'],info['data']['goods'])
        return out,snapshot
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            if path == '/api/info': raw,mime=json.dumps(info).encode(),'application/json'
            elif path in ('/api/dashboard','/api/dashboard/brief'):
                out,_ = fixture(self.headers.get('Referer',''))
                if path.endswith('/brief'):
                    query = parse_qs(parsed.query)
                    out = dashboard_brief.voice_reply(out['brief'],query.get('persona',['gamemaster'])[0],query.get('part',['detail'])[0],PreviewVoice(),info['data']['text'])
                raw,mime=json.dumps(out).encode(),'application/json'
            elif path == '/preview-voice.wav': raw,mime=tone.getvalue(),'audio/wav'
            elif path == '/api/captains': raw,mime=b'{"ok":true,"captains":[]}', 'application/json'
            elif path == '/events':
                self.send_response(200)
                self.send_header('Content-Type','text/event-stream')
                self.send_header('Cache-Control','no-store')
                self.end_headers()
                try:
                    while True:
                        _,snapshot = fixture(self.headers.get('Referer',''))
                        self.wfile.write(('data: '+json.dumps(snapshot)+'\n\n').encode())
                        self.wfile.flush()
                        time.sleep(5)
                except (BrokenPipeError, ConnectionResetError):
                    return
            elif path in ['/theme.css','/fonts.css'] or path.startswith(('/media/','/uploads/','/fonts/','/assets/')):
                try:
                    with urlopen(args.gallery+path,timeout=15) as r: raw,mime=r.read(),r.headers.get('Content-Type','application/octet-stream')
                except Exception as exc:
                    self.log_error('Preview asset %s: %s',path,exc)
                    return self.send_error(502)
            else:
                target=(ROOT/'web'/('dashboard.html' if path in ['/','/dashboard'] else path.lstrip('/'))).resolve()
                if not target.is_relative_to(ROOT/'web') or not target.is_file(): return self.send_error(404)
                raw,mime=target.read_bytes(),self.guess_type(str(target))
            self.send_response(200)
            self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(raw)
        def do_POST(self):
            if urlparse(self.path).path != '/api/voice/floor': return self.send_error(405)
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
            answer = voicefloor.FLOOR.ask(self.client_address[0],body.get('id'),body.get('op'),body.get('clip',''),role=body.get('role',''))
            raw=json.dumps(dict(answer,ok=True)).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    print(f'Dashboard sample preview: http://127.0.0.1:{args.port}/dashboard',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
if __name__ == '__main__': main()
