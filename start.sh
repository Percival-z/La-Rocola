#!/usr/bin/env bash
# Arranca Lavalink (si no está corriendo) y luego el bot de Discord.
set -euo pipefail
cd "$(dirname "$0")"

wait_port() {
  local i
  for i in $(seq 1 60); do
    if (exec 3<>/dev/tcp/127.0.0.1/2333) 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}

# Tokener de Spotify (token anónimo para las playlists)
if pgrep -f 'spotify_tokener\.py' >/dev/null 2>&1; then
  echo "[start] Tokener de Spotify ya está corriendo."
else
  echo "[start] Arrancando tokener de Spotify..."
  (cd tools && nohup ../.venv/bin/python spotify_tokener.py >tokener.log 2>&1 &)
  sleep 2
fi

# Credenciales de Spotify para Lavalink (application.yml las lee como
# ${SPOTIFY_CLIENT_ID:} / ${SPOTIFY_CLIENT_SECRET:} al arrancar Java).
if [ -f .env ]; then
  export SPOTIFY_CLIENT_ID="$(sed -n 's/^SPOTIFY_CLIENT_ID=//p' .env | head -1)"
  export SPOTIFY_CLIENT_SECRET="$(sed -n 's/^SPOTIFY_CLIENT_SECRET=//p' .env | head -1)"
  export LAVA_LINK_PASSWORD="$(sed -n 's/^LAVA_LINK_PASSWORD=//p' .env | head -1)"
fi

if pgrep -f 'java.*Lavalink\.jar' >/dev/null 2>&1; then
  echo "[start] Lavalink ya está corriendo."
else
  echo "[start] Arrancando Lavalink..."
  (cd lavalink && nohup ../jdk/bin/java -Xmx512M -jar Lavalink.jar >lavalink.log 2>&1 &)
  if wait_port; then
    echo "[start] Lavalink escuchando en 127.0.0.1:2333"
  else
    echo "[start] ERROR: Lavalink no abrió el puerto 2333. Revisa lavalink/lavalink.log" >&2
    exit 1
  fi
fi

echo "[start] Arrancando el bot..."
exec .venv/bin/python -m bot.main
