# Bot DS — Música en Discord (Lavalink + Wavelink)

Bot de Discord auto-hospedado con comandos de aplicación (slash commands) para reproducir
música por voz usando **Lavalink 4**, **Wavelink 3** y **LavaSrc** (Spotify) + plugin oficial de YouTube.

## Requisitos

- Python 3.10+ en Linux o **3.11+ en Windows**
- Un JDK 21 (ver la sección *Binarios*)
- Un token de bot de Discord en `.env` (ver `.env.example`)

## Binarios (no se suben al repo)

GitHub no admite archivos gigantes (el JDK pesa ~300 MB y `Lavalink.jar` ~96 MB),
así que `jdk/`, `*.jar` y los logs están en `.gitignore`. Después de clonar,
descarga lo que falta:

| Qué | Dónde | Destino |
|---|---|---|
| Lavalink 4.2.2 | [releases](https://github.com/lavalink-devs/Lavalink/releases/tag/4.2.2) → `Lavalink.jar` | `lavalink/Lavalink.jar` |
| Plugin LavaSrc 4.8.3 (Spotify) | [releases](https://github.com/topi314/LavaSrc/releases/tag/4.8.3) → `lavasrc-plugin-4.8.3.jar` | `lavalink/plugins/` |
| Plugin YouTube (snapshot `2be8e542`) | [Maven snapshots](https://maven.lavalink.dev/snapshots/dev/lavalink/youtube/youtube-plugin/2be8e542d3f6f178e048dca565892684c2e40177/youtube-plugin-2be8e542d3f6f178e048dca565892684c2e40177.jar) | `lavalink/plugins/` |
| JDK 21 | [Temurin](https://adoptium.net/temurin/releases/) → `.zip` | extraído como `jdk/` (Windows: `jdk\bin\java.exe`) |
| Configuración | `cp .env.example .env` y rellena | `.env` |

Los `.bak` de plugins son solo respaldos locales: se ignoran.

## Estructura

```
.env                  # token de Discord, credenciales Spotify, Lavalink, auto-join
requirements.txt
start.sh              # arranca tokener + Lavalink + bot (Linux)
stop.sh               # detiene los tres (Linux)
start.bat             # ídem en Windows (crea el .venv y instala pip solo)
stop.bat              # detiene los tres en Windows
jdk/                  # JDK portable (Temurin 21) — descargado, no va al repo
lavalink/
  Lavalink.jar        # servidor Lavalink 4.2.2 — descargado, no va al repo
  application.yml     # configuración (puerto 2333, password, plugins)
  plugins/            # lavasrc-plugin (Spotify) + youtube-plugin (snapshot) — descargados
  lavalink.log        # log del servidor (no va al repo)
tools/
  spotify_totp.py     # genera tokens anónimos de Spotify (secret v61 + TOTP)
  spotify_tokener.py  # servidor local que sirve ese token a LavaSrc (puerto 2334)
bot/
  main.py             # entrada: conexión a Discord + nodo Lavalink + auto-join
  cogs/music.py       # comandos slash
logs/bot.log          # log del bot (rotado, no va al repo)
.venv/                # entorno Python con discord.py + wavelink (no va al repo)
```

## Arranque

### Linux

```bash
./start.sh     # tokener de Spotify + Lavalink + bot en primer plano
./stop.sh      # detiene todo
```

### Windows

**Prerrequisitos (una sola vez):**

1. [Python 3.11+](https://www.python.org/downloads/) con la opción
   *Add python.exe to PATH* marcada (la dependencia `davey` solo tiene rueda
   de Windows desde la 3.11).
2. **JDK 21 para Windows**: descarga el `.zip` de
   [Temurin 21](https://adoptium.net/temurin/releases/) y extráelo **dentro de
   esta carpeta** para que exista `jdk\bin\java.exe`. (La carpeta `jdk/`
   incluida es de Linux y no sirve en Windows; también vale un JDK 21 en el
   `PATH` o en la variable `JAVA_HOME`.)

**Uso:**

```bat
start.bat        # primer arranque: crea .venv, instala requirements y arranca todo
stop.bat         # detiene todo (pregunta si forzar o esperar tu Ctrl+C)
stop.bat force   # detiene todo a la fuerza
```

- `start.bat` arranca el tokener y Lavalink en ventanas **minimizadas** (con
  sus logs) y el bot en la ventana **principal**.
- **Detener el bot:** `Ctrl+C` en su ventana → cierre elegante (desconecta la
  voz al instante). Si Windows pregunta «¿Terminar el lote de trabajo?»,
  responde `N`. No cierres la ventana con la **X**: eso mata el proceso sin
  desconectar la voz y Discord tarda hasta ~1 minuto en sacarlo del canal.
- `start.bat` detecta si el bot ya está corriendo y avisa.

⚠️ **Un solo bot a la vez:** el token de Discord solo admite una conexión. Si
el bot ya está corriendo en Linux, no lo arranques también en Windows (ni al
revés): se desconectan mutuamente.

El bot se auto-une al canal de voz indicado en `.env` (`AUTO_JOIN_GUILD` / `AUTO_JOIN_CHANNEL`)
y registra los comandos en ese servidor al instante.

## Comandos

| Comando | Descripción |
|---|---|
| `/play query [shuffle]` | Canción por nombre o enlace de playlist (Spotify / YouTube Music). `shuffle=True` baraja el orden. |
| `/pause` | Pausa |
| `/resume` | Reanuda |
| `/stop` | Detiene y vacía la cola |
| `/skip` | Salta a la siguiente |
| `/queue` | Muestra la cola |

- Texto libre: busca primero en **Spotify** (`spsearch:`) y si no hay resultados, en **YouTube Music** (`ytmsearch:`).
- Enlaces: se pasan tal cual a Lavalink (Spotify/YouTube los resuelven los plugins).

## Logs

- Lavalink: `lavalink/lavalink.log`
- Bot: `logs/bot.log` (rotado, también sale por consola)
- Tokener de Spotify: `tools/tokener.log`
- Dependencias en Windows: `logs/pip.log`

Para ver los fallos de reproducción (una pista que falla hace que el bot salte a la
siguiente):

```bash
grep 'Client \[' lavalink/lavalink.log | tail     # por qué falló cada cliente de YouTube
grep 'Failed to load' lavalink/lavalink.log       # cargas que fallaron
```

## Notas técnicas (por qué está así)

### Spotify: playlists vía Partner API + tokener local

Spotify restringió su API en 2026 (issue LavaSrc #358): el endpoint
`/playlists/{id}/items` devuelve `401 Valid user authentication required` con token de
app. Solución aplicada en `lavalink/application.yml`:

- `preferPartnerApi: true` → las playlists van por la Partner API (la del reproductor
  web), que no requiere usuario.
- `customTokenEndpoint: http://127.0.0.1:2334/spotify-token` → el token anónimo que
  usa esa API lo sirve `tools/spotify_tokener.py`, porque el extractor incluido en
  LavaSrc 4.8.3 quedó obsoleto: Spotify cambió el formato del "secret" en su bundle
  (ahora es un string con XOR, versión `61`) y exige `totpVer=61` en `/api/token`.
  El tokener replica el flujo actual del reproductor web y cachea el token.
- La **búsqueda** (`spsearch:`) no se ve afectada: usa directamente
  `accounts.spotify.com/api/token` con el client id/secret de la app.

### YouTube: snapshot del plugin + cipher remoto

- `plugins/youtube-plugin-2be8e542.jar` es un **snapshot** (nuevo 17 sep 2026) del
  plugin oficial; la release 1.18.2 fallaba en varios videos con
  "No supported audio streams available" / "Sign in to confirm you're not a bot"
  (issue youtube-source #240). El `.bak` es la release anterior.
- `plugins.youtube.remoteCipher.url: https://cipher.kikkia.dev/` → extractor de
  cifrado remoto gratuito del mantenedor del plugin; sin él YouTube no entrega URLs
  de audio.
- Los clientes habilitados: `TV, TVHTML5_SIMPLY, WEB, MUSIC, WEBEMBEDDED, ANDROID_VR, MWEB`.
