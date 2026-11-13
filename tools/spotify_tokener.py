#!/usr/bin/env python3
"""Servidor de tokens anónimos de Spotify para LavaSrc (customTokenEndpoint).

LavaSrc llama a http://127.0.0.1:2334/spotify-token cuando necesita el token
anónimo que usa la Partner API (playlists). Este servidor replica el flujo del
reproductor web actual de Spotify (secret XOR v61 -> TOTP -> /api/token) y
cachea el token hasta poco antes de expirar.

Uso:
    python3 tools/spotify_tokener.py [puerto]
"""
from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from spotify_totp import fetch_anonymous_token

CACHE_MARGIN_MS = 90_000  # refresca 90 s antes de expirar

_lock = threading.Lock()
_cache: dict | None = None
_cache_ts: float = 0.0


def get_token() -> dict:
    global _cache, _cache_ts
    with _lock:
        now_ms = time.time() * 1000
        if _cache and now_ms < _cache.get("accessTokenExpirationTimestampMs", 0) - CACHE_MARGIN_MS:
            return _cache
        _cache = fetch_anonymous_token()
        _cache_ts = time.time()
        print(f"[tokener] token renovado, expira en "
              f"{(_cache['accessTokenExpirationTimestampMs'] - now_ms) / 60000:.1f} min", flush=True)
        return _cache


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path.split("?")[0] != "/spotify-token":
            self.send_response(404)
            self.end_headers()
            return
        try:
            body = json.dumps(get_token()).encode()
        except Exception as e:  # noqa: BLE001
            body = json.dumps({"error": str(e)}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silencioso
        pass


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 2334
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"[tokener] escuchando en http://127.0.0.1:{port}/spotify-token", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
