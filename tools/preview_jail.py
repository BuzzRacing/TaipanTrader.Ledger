"""Preview the real jail screens with disposable state: python tools/preview_jail.py."""
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cast
import config
import fonts
import media
import strings


def build_preview(cfg):
    fixture = json.dumps({"strings": strings.resolve(cfg), "ports": cfg["ports"],
                         "cast": cast.public_cast(cfg), "media": media.public(cfg)}, ensure_ascii=True).replace("</", "<\\/")
    html = '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Jail layout preview</title><link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/deck.css">
    <link rel="stylesheet" href="/jail.css"><link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/fonts.css">
    </head><body class="player"><div id="app"></div><script src="/common.js"></script><script src="/media.js"></script>
    <script>const fixture=FIXTURE;T=fixture.strings;Media.setup(fixture.media);
    const D={ports:fixture.ports},VS={cast:fixture.cast};
    let S={phase:'port',turn:2,waiting:[],me:{name:'Preview Captain',cash:10000,log:[],jail:{}}};
    const port=new URLSearchParams(location.search).get('port')||'hongkong';
    const jail={port,warden:'warden_'+port,months:3,served:0,left:3,fresh:true,charge:'contraband'};
    const mode=new URLSearchParams(location.search).get('stage')||'arrest';
    if(mode==='plea')S.me.jail.plea={...jail,id:'preview',amount:12000,opts:[{months:0,pay:12000,share:1},{months:1,pay:6000,share:.5},{months:3,pay:3000,share:.25}]};
    else if(mode==='release')S.me.jail.freed={...jail,turn:2};
    else S.me.jail.jail={...jail,fresh:mode==='arrest',served:mode==='month'?1:0,left:mode==='month'?2:3};
    async function act(type,data){
      if(type==='plea'){delete S.me.jail.plea;S.me.jail.jail={...jail,months:data.months||1};}
      if(type==='jail_serve'){
        const j=S.me.jail.jail;
        if(j.fresh)j.fresh=false;
        else if(--j.left<=0){S.me.jail={freed:{...j,turn:++S.turn}};}
        else {j.served++;S.turn++;}
      }
      if(type==='jail_free'){S.me.jail={};document.querySelector('#app').textContent='Back at port (preview complete)';}
      Jail.sync();return true;
    }</script><script src="/jail.js"></script><script>Jail.sync();</script></body></html>'''.replace('FIXTURE', fixture)

    return html


def main():
    cfg = config.load()
    html = build_preview(cfg)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT / 'web'), **kwargs)

        def do_GET(self):
            path = self.path.split('?')[0]
            content = {'/': (html, 'text/html'), '/theme.css': (config.theme_css(cfg), 'text/css'),
                       '/fonts.css': (config.fonts_css(cfg, fonts.local_css()), 'text/css')}.get(path)
            if not content:
                target = (ROOT / 'web' / unquote(path).lstrip('/')).resolve()
                if not target.is_relative_to(ROOT / 'web') or not target.is_file() or target.suffix.lower() not in {
                    '.css', '.js', '.png', '.jpg', '.jpeg', '.webp', '.woff', '.woff2', '.ttf'}:
                    return self.send_error(404)
                return super().do_GET()
            raw = content[0].encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', content[1] + '; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    print('Jail preview: http://localhost:18881/?stage=arrest (also month, release, plea)', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 18881), Handler).serve_forever()


if __name__ == '__main__':
    main()
