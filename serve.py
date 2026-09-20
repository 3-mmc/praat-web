#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Serve praat-web, fetching the praat-wasm package on first run.

    python3 serve.py                 # http://127.0.0.1:8710
    python3 serve.py --port 9000
    python3 serve.py --host 0.0.0.0  # reachable from the LAN

Standard library only — no pip install, no build step. The one external thing is
the praat-wasm npm tarball (~24 MB), downloaded once into ./vendor/ and cached.
If you would rather fetch it yourself:

    npm pack praat-wasm@6.4.6200 && tar xzf praat-wasm-6.4.6200.tgz
    mv package vendor

praat-wasm is GPL-3.0-or-later, as is this project. It is not vendored into git
because 24 MB of binary does not belong in a source repository.
"""
import argparse
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import sys
import tarfile
import urllib.request

HERE = Path(__file__).resolve().parent
VENDOR = Path(os.environ.get('PRAAT_WASM_DIR', HERE / 'vendor'))
PKG = 'praat-wasm'
VERSION = '6.4.6200'
TARBALL = f'https://registry.npmjs.org/{PKG}/-/{PKG}-{VERSION}.tgz'

TYPES = {
    '.html': 'text/html', '.mjs': 'text/javascript', '.js': 'text/javascript',
    '.wasm': 'application/wasm', '.json': 'application/json', '.css': 'text/css',
    '.map': 'application/json', '.ts': 'text/plain', '.svg': 'image/svg+xml',
}


def ensure_vendor() -> None:
    """Download and unpack praat-wasm unless it is already there."""
    if (VENDOR / 'js' / 'worker-client.mjs').is_file():
        return
    print(f'praat-wasm not found at {VENDOR}', file=sys.stderr)
    print(f'downloading {TARBALL} (~24 MB, once)…', file=sys.stderr)
    VENDOR.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(TARBALL, timeout=300) as r:
        blob = r.read()
    with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as tf:
        for member in tf.getmembers():
            # npm tarballs put everything under "package/"; strip it, and refuse
            # any path that would escape the vendor directory.
            name = member.name.split('/', 1)[-1] if member.name.startswith('package/') else None
            if not name or member.isdev() or member.issym() or member.islnk():
                continue
            dest = (VENDOR / name).resolve()
            if not str(dest).startswith(str(VENDOR.resolve())):
                continue
            if member.isdir():
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            src = tf.extractfile(member)
            if src:
                dest.write_bytes(src.read())
    if not (VENDOR / 'js' / 'worker-client.mjs').is_file():
        sys.exit('praat-wasm did not unpack as expected')
    print(f'praat-wasm {VERSION} ready in {VENDOR}', file=sys.stderr)


class Handler(BaseHTTPRequestHandler):
    server_version = 'praat-web'

    def log_message(self, fmt, *a):
        print(f'{self.address_string()} {fmt % a}', flush=True)

    def resolve(self):
        path = self.path.split('?', 1)[0]
        # Tolerate being mounted under a prefix by a reverse proxy.
        for marker in ('/upstream/praat/', '/upstream/praat'):
            if path.startswith(marker):
                path = path[len(marker):]
                break
        path = path.lstrip('/')
        if path in ('', 'index.html'):
            return HERE / 'index.html'
        base, rel = (VENDOR, path[len('vendor/'):]) if path.startswith('vendor/') else (HERE, path)
        target = (base / rel).resolve()
        if not str(target).startswith(str(base.resolve())):
            return None
        return target if target.is_file() else None

    def do_GET(self):
        if self.path.split('?', 1)[0].rstrip('/').endswith('/health'):
            body = json.dumps({'status': 'ok', 'service': 'praat-web'}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        target = self.resolve()
        if target is None:
            self.send_error(404, 'Not found')
            return
        data = target.read_bytes()
        ctype = TYPES.get(target.suffix, 'application/octet-stream')
        if ctype.startswith(('text/', 'application/json')):
            ctype += '; charset=utf-8'
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        if target.suffix in ('.wasm', '.mjs'):
            self.send_header('Cache-Control', 'public, max-age=31536000, immutable')
        self.end_headers()
        self.wfile.write(data)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Serve praat-web.')
    ap.add_argument('--port', type=int, default=8710)
    ap.add_argument('--host', default='127.0.0.1')
    args = ap.parse_args()
    ensure_vendor()
    print(f'praat-web on http://{args.host}:{args.port}', flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
