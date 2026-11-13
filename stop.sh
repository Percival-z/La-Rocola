#!/usr/bin/env bash
# Detiene el bot, el tokener y Lavalink. Espera el cierre elegante (que es el
# que desconecta la voz de Discord al instante) y solo fuerza con SIGKILL si
# el proceso no sale en ~2 segundos.
cd "$(dirname "$0")"

detener() {
  local patron="$1" nombre="$2" pid i
  pid=$(pgrep -f "$patron" | head -1)
  if [ -z "$pid" ]; then
    echo "[stop] $nombre no estaba corriendo."
    return
  fi
  pkill -f "$patron" # SIGTERM: el bot lo convierte en cierre elegante
  for i in $(seq 1 20); do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "[stop] $nombre detenido."
      return
    fi
    sleep 0.1
  done
  pkill -9 -f "$patron" 2>/dev/null && echo "[stop] $nombre forzado (SIGKILL)."
}

detener 'python -m bot\.main' "Bot"
detener 'spotify_tokener\.py' "Tokener de Spotify"
detener 'java.*Lavalink\.jar' "Lavalink"
