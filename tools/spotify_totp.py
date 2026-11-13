#!/usr/bin/env python3
"""Genera un token anónimo de Spotify replicando el flujo del plugin LavaSrc
(SpotifyTokenTracker) con el formato ACTUAL de secret de Spotify (XOR + version).

Uso directo (prueba):
    python3 tools/spotify_totp.py
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import struct
import sys
import time
import urllib.parse
import urllib.request

UA = "curl/8.5.0"  # con UA de Apache-HttpClient Spotify sirve un bundle SIN secret
HOME = "https://open.spotify.com/"
TOKEN_URL = (
    "https://open.spotify.com/api/token"
    "?reason=init&productType=web-player&totp={totp}&totpVer={ver}&ts={ts}"
)

SECRET_RE = re.compile(r"\{secret:\s*(['\"])(?P<s>(?:\\.|(?!\1).)*)\1\s*,\s*version:\s*(\d+)")


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    if data[:2] == b"\x1f\x8b":  # gzip magic bytes
        import gzip
        data = gzip.decompress(data)
    return data


def get_secret_string() -> tuple[str, int]:
    """Toma el primer {secret:'...',version:N} del script mobile-web-player actual."""
    html = _fetch(HOME).decode("utf-8", "replace")
    urls = re.findall(r'src="(https://open\.spotifycdn\.com/[^"]+mobile-web-player[^"]*\.js)"', html)
    urls = [u for u in urls if "vendor" not in u]
    if not urls:
        raise RuntimeError("no se encontró el script mobile-web-player en la homepage")
    js = _fetch(urls[0]).decode("utf-8", "replace")
    m = SECRET_RE.search(js)
    if not m:
        raise RuntimeError(f"no se encontró secret en {urls[0]}")
    # unescape simple de comillas/\\ dentro de la cadena JS
    raw = m.group("s")
    raw = raw.replace(r"\'", "'").replace(r"\"", '"').replace(r"\\", "\\")
    return raw, int(m.group(3))


def transform(secret_str: str) -> bytes:
    """XOR por posición con (i %% 33 + 9) y decimales concatenados como BYTES ASCII.
    Replica el decoder JS actual de Spotify:
        i = t.split("").map((c,i) => c.charCodeAt(0) ^ i%33+9)
        r = Buffer.from(i.join(""), "utf8").toString("hex")
        key = Buffer.from(r, "hex")   ->  == i.join("").encode("utf8")"""
    i = [ord(c) ^ (idx % 33 + 9) for idx, c in enumerate(secret_str)]
    return "".join(str(x) for x in i).encode("utf-8")


def totp(key: bytes, now_ms: int, period: int = 30, digits: int = 6) -> str:
    counter = (now_ms // 1000) // period
    h = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    code = ((h[o] & 0x7F) << 24 | h[o + 1] << 16 | h[o + 2] << 8 | h[o + 3]) % (10 ** digits)
    return f"{code:0{digits}d}"


def fetch_anonymous_token() -> dict:
    """Devuelve {'accessToken': str, 'accessTokenExpirationTimestampMs': int}
    usando los parámetros exactos del player actual (AK/AY del bundle)."""
    secret_str, version = get_secret_string()
    key = transform(secret_str)
    ts = int(time.time() * 1000)
    code = totp(key, ts, 30, 6)
    q = urllib.parse.urlencode({
        "reason": "init",
        "productType": "web_player",
        "totp": code,
        "totpServer": "unavailable",
        "totpVer": str(version),
    })
    req = urllib.request.Request(f"https://open.spotify.com/api/token?{q}",
                                 headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:250]}")
    if "accessToken" not in data:
        raise RuntimeError(f"respuesta sin accessToken: {str(data)[:250]}")
    return data


if __name__ == "__main__":
    s, ver = get_secret_string()
    print(f"secret extraído (v{ver}, {len(s)} chars): {s[:12]}...")
    k = transform(s)
    print(f"key ({len(k)} bytes): {k[:16]!r}...")
    tok = fetch_anonymous_token()
    print("TOKEN OK:", {k2: (str(v)[:50] + "..." if k2 == "accessToken" else v) for k2, v in tok.items()})
