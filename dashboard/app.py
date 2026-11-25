"""Run from repository root: python dashboard/app.py (local browser at :8050)."""
from __future__ import annotations

import argparse
import csv
import io
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from service import DashboardService, ModelUnavailable

STATIC = Path(__file__).with_name('static')


def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        def send(self, status, body, content_type='application/json; charset=utf-8', filename=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, allow_nan=False)
            if isinstance(body, str):
                body = body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            if filename:
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlsplit(self.path)
            args = parse_qs(parsed.query)
            def arg(name):
                if name not in args or len(args[name]) != 1:
                    raise ValueError(f'Provide one {name} value.')
                return args[name][0]
            try:
                if parsed.path == '/api/meta':
                    result = service.metadata()
                elif parsed.path == '/api/history':
                    result = service.history(arg('start'), arg('end'))
                elif parsed.path == '/api/forecast':
                    result = service.forecast(arg('timestamp'))
                elif parsed.path == '/api/metrics':
                    result = service.metrics()
                elif parsed.path == '/api/export':
                    return self.send(200, service.export(arg('start'), arg('end')), 'text/csv; charset=utf-8', 'building-history.csv')
                else:
                    files = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css', '/favicon.svg': 'favicon.svg', '/fonts/SourceSans3.ttf': 'fonts/SourceSans3.ttf'}
                    if parsed.path not in files:
                        return self.send(404, {'error': 'Page not found.'})
                    path = STATIC / files[parsed.path]
                    return self.send(200, path.read_bytes(), mimetypes.guess_type(path)[0] or 'application/octet-stream')
                self.send(200, result)
            except (ValueError, FileNotFoundError) as exc:
                self.send(400, {'error': str(exc)})
            except ModelUnavailable as exc:
                self.send(503, {'error': str(exc)})
            except Exception as exc:
                print(f'Dashboard error: {type(exc).__name__}: {exc}')
                self.send(500, {'error': 'The dashboard could not complete this operation. Check the server terminal.'})

        def do_POST(self):
            # Same-origin JSON only. There are no physical commands or arbitrary path/file writes.
            origin = self.headers.get('Origin')
            if origin and origin != f'http://{self.headers.get("Host")}':
                return self.send(403, {'error': 'Cross-origin requests are not permitted.'})
            if self.path != '/api/scenario':
                return self.send(404, {'error': 'Endpoint not found.'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 4096:
                    raise ValueError('Provide a JSON request smaller than 4 KB.')
                if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    raise ValueError('Use application/json.')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError('Provide a JSON object.')
                self.send(200, service.scenario(payload.get('start'), payload.get('end'), payload.get('shift', 1), payload.get('lighting', 'occupancy')))
            except (ValueError, TypeError) as exc:
                self.send(400, {'error': str(exc)})
            except Exception as exc:
                print(f'Scenario error: {type(exc).__name__}: {exc}')
                self.send(500, {'error': 'Simulation failed. Check the server terminal.'})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8050)
    parser.add_argument('--csv', type=Path, default=None)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(DashboardService(args.csv)))
    print(f'SDP dashboard: http://127.0.0.1:{args.port}', flush=True)
    print('Local synthetic-data dashboard. Press Ctrl+C to stop.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
