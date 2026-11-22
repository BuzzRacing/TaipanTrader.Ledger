"""Read-only design review. Public catalog only; no saves, seat tokens or game actions."""
import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gallery', default='http://192.168.1.69:8765')
    parser.add_argument('--port', type=int, default=18885)
    args = parser.parse_args()
    gallery = args.gallery.rstrip('/')
    with urlopen(gallery + '/api/info?family=1', timeout=15) as response:
        info = json.load(response)
    with urlopen(gallery + '/api/captains', timeout=15) as response:
        captains = json.load(response)
    if not info['media'].get('family'):
        raise RuntimeError('Clean-only catalog required for the public screen preview')
    catalog = info['media']['items']
    allowed_images = {item['u'] for subjects in catalog.values() for items in subjects.values()
                      for item in items if item['t'] == 'image'}

    def clean_picture(kind, subject, current):
        pictures = [item for item in catalog.get(kind, {}).get(subject, []) if item['t'] == 'image']
        if current in {item['u'] for item in pictures}:
            return current
        return next((item['u'] for item in pictures), '')

    for captain in captains.get('captains', []):
        captain['portrait'] = clean_picture('captain', captain['cid'], captain.get('portrait'))
        for house in captain.get('houses', []):
            house['image'] = clean_picture('house', house['hid'], house.get('image'))
    data = info['data']
    fixture = json.dumps({'gallery': gallery, 'captains': captains,
                          'media': info['media'], 'cast': info['voice'].get('cast', {}),
                          'brand': data['brand'], 'lengths': data['lengths'],
                          'difficulty': data.get('difficulty'), 'ports': data['ports']}).encode()

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            path = unquote(self.path.split('?')[0])
            if path == '/fixture.json':
                raw, mime = fixture, 'application/json'
            elif path in ('/theme.css', '/fonts.css') or path.startswith(('/media/', '/uploads/', '/assets/', '/fonts/')):
                if '..' in path.split('/'):
                    return self.send_error(400)
                if path not in ('/theme.css', '/fonts.css') and not path.startswith('/fonts/') and path not in allowed_images:
                    return self.send_error(403, 'Image is not in the clean-only catalog')
                try:
                    with urlopen(gallery + path + ('?family=1' if path == '/theme.css' else ''), timeout=15) as response:
                        raw, mime = response.read(), response.headers.get('Content-Type', 'application/octet-stream')
                except Exception as exc:
                    self.log_error('Artwork fetch failed: %s: %s', path, exc)
                    return self.send_error(502, 'Artwork unavailable')
            else:
                target = (ROOT / 'design' / 'thresholds' / ('index.html' if path == '/' else path.lstrip('/'))).resolve()
                if not target.is_relative_to(ROOT / 'design' / 'thresholds') or not target.is_file():
                    return self.send_error(404)
                raw, mime = target.read_bytes(), self.guess_type(str(target))
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(raw)

    print(f'Design review: http://127.0.0.1:{args.port} (read-only; sample voyage results)', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
