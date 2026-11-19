"""Serve the real Options UI with disposable in-memory data; never opens a saved game."""
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


def main():
    cfg = config.load()
    library = media.public(cfg)
    portraits = next(iter(library["items"].get("captain", {}).values()), [])
    crests = next(iter(library["items"].get("house", {}).values()), [])

    def pictures(items):
        return [{"id": p["id"], "url": p["u"], "primary": i == 0} for i, p in enumerate(items) if p["t"] == "image"]

    data = {"ok": True, "captain": {"name": "Anthony", "title": "Master of the China Seas"},
            "house": {"name": "The Crimson Company", "color": "#c9a34e"},
            "portraits": pictures(portraits), "crests": pictures(crests),
            "painting": {}, "mode": "Merchant", "table_family": False, "admin": False}
    fixture = json.dumps({"media": library, "cast": media.safe_cast(cast.public_cast(cfg), cfg),
                          "brand": cfg["brand"], "options": data}, ensure_ascii=True).replace("</", "<\\/")
    html = '''<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Captain Options · isolated preview</title><link rel="stylesheet" href="/style.css">
    <link rel="stylesheet" href="/deck.css"><link rel="stylesheet" href="/options.css">
    <link rel="stylesheet" href="/theme.css"><link rel="stylesheet" href="/fonts.css"></head>
    <body class="player"><button data-act="me" onclick="Options.open()" style="margin:2rem">Captain Options</button>
    <div id="toast" role="status"></div><script src="/common.js"></script><script src="/media.js"></script>
    <script>
    const fixture = FIXTURE;
    Media.setup(fixture.media);
    let D={start_year:1860,brand:fixture.brand}, VS={cast:fixture.cast}, token='preview',stream=null;
    let S={turn:14,years:5,turns_left:46,date:'March 1861',me:{id:'p1',name:'Anthony',firm:'The Crimson Company',
      portrait:fixture.options.portraits[0]?.url||'',crest:''},players:[
      {id:'p1',name:'Anthony',firm:'The Crimson Company',present:true},
      {id:'p2',name:'Victoria',firm:'Jade & Silk',ready:true},
      {id:'p3',name:'James',firm:'East India Trading',present:false}]};
    for(let i=0;i<12;i++)T['mon.'+i]=['January','February','March','April','May','June','July','August','September','October','November','December'][i];
    function toast(s){document.querySelector('#toast').textContent=s;}
    async function post(path,body){
      if(body.op==='house'){fixture.options.house.name=body.name;fixture.options.house.color=body.color;S.me.firm=body.name;}
      if(body.op==='pick'){for(const p of fixture.options[body.what==='portrait'?'portraits':'crests'])p.primary=p.id===body.id;}
      if(body.op==='generate')fixture.options.painting[body.what==='portrait'?'captain':'house']=1;
      return {ok:true,msg:'Preview updated (memory only)'};
    }
    const originalFetch=window.fetch.bind(window);
    window.fetch=(url,...args)=>String(url).startsWith('/api/options')?Promise.resolve(new Response(JSON.stringify(fixture.options))):originalFetch(url,...args);
    </script><script src="/options.js"></script><script>Options.open();</script></body></html>'''.replace("FIXTURE", fixture)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

        def do_GET(self):
            path = self.path.split("?")[0]
            content = {"/": (html, "text/html"), "/theme.css": (config.theme_css(cfg), "text/css"),
                       "/fonts.css": (config.fonts_css(cfg, fonts.local_css()), "text/css")}.get(path)
            if not content:
                target = (ROOT / "web" / unquote(path).lstrip("/")).resolve()
                web = (ROOT / "web").resolve()
                if not target.is_relative_to(web) or not target.is_file() or target.suffix.lower() not in {
                    ".css", ".js", ".png", ".jpg", ".jpeg", ".webp", ".woff", ".woff2", ".ttf"}:
                    return self.send_error(404)
                return super().do_GET()
            raw = content[0].encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", content[1] + "; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    print("Options preview: http://localhost:18878 (all edits stay in memory)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 18878), Handler).serve_forever()


if __name__ == "__main__":
    main()
