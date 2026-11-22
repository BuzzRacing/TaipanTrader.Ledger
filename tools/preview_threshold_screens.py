"""Serve the real public-screen renderers with disposable fixtures, never a saved game."""
import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import unquote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import strings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gallery', default='http://192.168.1.69:8765')
    parser.add_argument('--port', type=int, default=18886)
    args = parser.parse_args()
    gallery = args.gallery.rstrip('/')
    with urlopen(gallery + '/api/info?family=1', timeout=15) as response:
        info = json.load(response)
    with urlopen(gallery + '/api/captains', timeout=15) as response:
        captains = json.load(response)
    assert info['media']['family'], 'Clean catalog required'
    allowed = {i['u'] for subjects in info['media']['items'].values() for items in subjects.values()
               for i in items if i['t'] == 'image'}
    for c in captains['captains']:
        pictures = info['media']['items'].get('captain', {}).get(c['cid'], [])
        c['portrait'] = next((i['u'] for i in pictures if i['t'] == 'image'), '')
        for h in c['houses']:
            h['image'] = h.get('image') if h.get('image') in allowed else ''
    info['data']['text'].update({k:v for k,v in strings.EN.items() if k.startswith('threshold.')})
    info['voice']['enabled'] = False
    fixture = json.dumps({'info':info,'captains':captains}).replace('</','<\\/')
    player = (ROOT / 'web/player.js').read_text(encoding='utf-8')
    functions = player[player.index('/* Saved Captains'):player.index('/* The header plaques.')]
    helpers = player[player.index('const val ='):player.index('function quote(')]
    control = player[player.index('function newGameControl('):player.index('/* -------------------------------------------------------------- screens')]
    html = '''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Crimson Ledger · real screen preview</title>
    <link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/deck.css"><link rel="stylesheet" href="/ceremony.css">
    <link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/fonts.css"><link rel="stylesheet" href="/thresholds.css">
    </head><body class="player threshold-screen"><div id="app"><div class="solo"></div></div><div id="toast" role="status"></div>
    <script src="/ranks.js"></script><script src="/common.js"></script><script src="/wordmark.js"></script>
    <script src="/ceremony.js"></script><script src="/thresholds.js"></script><script src="/preview.js"></script></body></html>'''
    script = '''const fixture=FIXTURE;
    let D=fixture.info.data,VS=fixture.info.voice;
    T=D.text; TOK=D.tokens; CUR=D.brand.currency; COLORS=D.colors; Ranks.configure(D);
    const app=document.querySelector('#app'),ui={vals:{},confirmNew:false};
    const Certificate={};
    const screen=new URLSearchParams(location.search).get('screen')||'join';
    let rosterCaps=fixture.captains.captains;
    let players=rosterCaps.map((c,i)=>({id:'p'+i,name:c.name,firm:c.houses[0]?.name||'House',portrait:c.portrait,
      crest:c.houses[0]?.image||'',color:i,host:i===0,present:i!==2,worth:[12480000,8240000,1860000][i]||0,rank:'Taipan',ships:3,port:'hongkong'}));
    if(screen==='solo')players=players.slice(0,1);
    if(screen==='tie'&&players[1])players[1].worth=players[0].worth;
    if(screen==='negative')players.forEach((p,i)=>p.worth=-1000*(i+1));
    if(screen==='empty'){fixture.captains.captains=[];players=[];}
    if(screen==='nohouse'){fixture.captains.captains[0].houses=[];ui.capSel=fixture.captains.captains[0].cid;}
    let S={cfg:1,game_id:'preview-'+screen,join_url:'http://preview.invalid',phase:['join','empty','nohouse'].includes(screen)?'lobby':['lobby','guest'].includes(screen)?'lobby':'ended',
      me:['join','empty','nohouse'].includes(screen)?null:{...players[screen==='guest'?1:0]},players,years:D.lengths[0],date:'December 1864'};
    HELPERS
    CONTROL
    FUNCTIONS
    CAPS=fixture.captains; capsAt=Date.now();
    const initialFetch=window.fetch.bind(window);
    window.fetch=(url,...args)=>{
      if(String(url).startsWith('/api/captains'))return Promise.resolve(new Response(JSON.stringify(fixture.captains)));
      return initialFetch(url,...args);
    };
    function toast(message){document.querySelector('#toast').textContent=message;}
    function render(){app.querySelector('.solo').innerHTML=!S.me?joinScreen():S.phase==='lobby'?lobbyScreen():endScreen();}
    app.addEventListener('input',event=>{if(event.target.dataset.k)ui.vals[event.target.dataset.k]=event.target.value;});
    app.addEventListener('click',event=>{
      const button=event.target.closest('[data-act]');if(!button||button.disabled)return;const a=button.dataset.act;
      if(a==='cap_pick'){ui.capSel=button.dataset.cid;ui.vals.pin='';}
      else if(a==='cap_back'){ui.capSel='';ui.vals.pin='';}
      else if(a==='cap_house')ui.capHouse=button.dataset.hid;
      else if(a==='cap_join'){const c=fixture.captains.captains.find(c=>c.cid===ui.capSel);S.me={...players[0],name:c.name,firm:c.houses[0].name};}
      else if(a==='years')S.years=+button.dataset.y;
      else if(a==='newgame_ask')ui.confirmNew=true;
      else if(a==='newgame_no')ui.confirmNew=false;
      else if(a==='threshold_retry')return Thresholds.retry();
      else if(a==='threshold_book_retry')return Thresholds.retryBook();
      else return toast('Isolated preview: '+a+' does not change a real game.');
      render();
    });
    render();'''.replace('FIXTURE',fixture).replace('HELPERS',helpers).replace('CONTROL',control).replace('FUNCTIONS',functions)

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            path = unquote(self.path.split('?')[0])
            if path == '/':
                raw,mime = html.encode(),'text/html'
            elif path == '/preview.js':
                raw,mime = script.encode(),'text/javascript'
            elif path == '/api/info':
                raw,mime = json.dumps(info).encode(),'application/json'
            elif path == '/api/captains':
                raw,mime = json.dumps(captains).encode(),'application/json'
            elif path == '/api/finale':
                mode = self.headers.get('Referer','').split('screen=')[-1]
                houses = [{'id':'p0','voyages':54,'won':8,'trades':120,'best_sale':{'profit':860000}}]
                book = {'ok':True,'game':'preview-'+(mode if mode!='join' else 'end'),'houses':houses,'honours':[{'key':'golden_sale','id':'p0'}]}
                if mode == 'missing':
                    book = {'ok':False}
                raw,mime = json.dumps(book).encode(),'application/json'
            elif path in ('/theme.css','/fonts.css') or path.startswith(('/media/','/uploads/','/assets/','/fonts/')):
                if '..' in path.split('/') or (path not in ('/theme.css','/fonts.css') and not path.startswith('/fonts/') and path not in allowed):
                    return self.send_error(403)
                try:
                    with urlopen(gallery + path, timeout=15) as response:
                        raw,mime = response.read(),response.headers.get('Content-Type','application/octet-stream')
                except Exception as exc:
                    self.log_error('Preview media: %s: %s',path,exc)
                    return self.send_error(502)
            else:
                target=(ROOT / 'web' / path.lstrip('/')).resolve()
                if not target.is_relative_to(ROOT / 'web') or not target.is_file() or target.suffix not in ('.css','.js'):
                    return self.send_error(404)
                raw,mime=target.read_bytes(),self.guess_type(str(target))
            self.send_response(200)
            self.send_header('Content-Type',mime+'; charset=utf-8' if mime.startswith('text/') else mime)
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(raw)

    print(f'Real screen preview: http://127.0.0.1:{args.port}/?screen=join (no saved game)',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()


if __name__ == '__main__':
    main()
