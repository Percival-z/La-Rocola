"""Punto de entrada del bot de Discord (Lavalink + Wavelink)."""

from __future__ import annotations

import logging
import logging.handlers
import os
import signal
import sys
from pathlib import Path

# Raíz del proyecto en sys.path para importar el paquete `bot`.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import discord
import wavelink
from discord import app_commands
from discord.ext import commands

# Consola + archivo rotado (para poder revisar lo que pasó en Discord después).
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            LOG_DIR / "bot.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        ),
    ],
)
log = logging.getLogger("bot")

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(
    command_prefix=commands.when_mentioned,
    intents=intents,
    application_id=int(os.getenv("DS_APP_ID") or 0) or None,
)


async def setup_hook() -> None:
    """Conecta el nodo Lavalink y carga el cog de música."""
    uri = os.getenv("LAVA_LINK_URI", "http://127.0.0.1:2333")
    password = os.getenv("LAVA_LINK_PASSWORD", "")

    try:
        node = wavelink.Node(identifier="botds", uri=uri, password=password, client=bot)
    except TypeError:
        node = wavelink.Node(identifier="botds", uri=uri, password=password)

    await wavelink.Pool.connect(nodes=[node], client=bot)
    await bot.load_extension("bot.cogs.music")
    log.info("Nodo Lavalink listo: %s", uri)


# discord.py llama a `self.setup_hook()`; hay que registrarlo en la instancia.
bot.setup_hook = setup_hook


async def _setup_guild(guild: discord.Guild) -> None:
    """Sincroniza los comandos y hace auto-join en el servidor objetivo (una sola vez)."""
    done = getattr(bot, "_configured", None)
    if done is None:
        done = bot._configured = set()
    if guild.id in done:
        return

    guild_name = (os.getenv("AUTO_JOIN_GUILD") or "").strip()
    if guild_name and guild.name != guild_name:
        return
    done.add(guild.id)

    # Comandos de aplicación en el servidor: disponibles al instante.
    try:
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        log.info("Sincronizados %d comandos en '%s'", len(synced), guild.name)
    except discord.HTTPException:
        log.exception("No se pudieron sincronizar los comandos")

    # Auto-union al canal de voz.
    channel_name = (os.getenv("AUTO_JOIN_CHANNEL") or "").strip()
    channel = discord.utils.get(guild.voice_channels, name=channel_name) if channel_name else None
    if channel is None:
        if channel_name:
            log.warning("Canal de voz '%s' no encontrado en '%s'", channel_name, guild.name)
        return

    vc = guild.voice_client
    if isinstance(vc, wavelink.Player) and vc.connected:
        return
    try:
        await channel.connect(cls=wavelink.Player)
        log.info("Auto-unido a '%s' -> %s", guild.name, channel.name)
    except Exception:
        log.exception("No se pudo unir al canal '%s'", channel.name)


@bot.event
async def on_ready() -> None:
    log.info("Conectado como %s (%s)", bot.user, getattr(bot.user, "id", "?"))
    if getattr(bot, "_started", False):
        return
    bot._started = True
    for guild in bot.guilds:
        await _setup_guild(guild)
    if not bot.guilds:
        log.warning("El bot no está en ningún servidor todavía: invítalo con el enlace de OAuth2.")


@bot.event
async def on_guild_join(guild: discord.Guild) -> None:
    # discord.py 2.7 emite `guild_join` cuando el bot entra a un servidor.
    log.info("Entré al servidor '%s'", guild.name)
    await _setup_guild(guild)


@bot.tree.error
async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    """Responde siempre a errores de comandos (evita el estado 'pensando' eterno)."""
    original = error.original if isinstance(error, app_commands.CommandInvokeError) else error
    name = interaction.command.name if interaction.command else "?"
    log.exception("Error en el comando /%s", name)
    content = f"❌ Error al ejecutar `/{name}`: `{original}`"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=True)
        else:
            await interaction.response.send_message(content, ephemeral=True)
    except discord.HTTPException:
        pass


def main() -> None:
    token = os.getenv("DS_TOKEN")
    if not token:
        log.error("Falta DS_TOKEN en el archivo .env")
        sys.exit(1)

    # SIGTERM (pkill / shutdown / systemd) debe ser tan elegante como Ctrl+C:
    # de lo contrario el proceso muere sin `voice.disconnect()` y Discord tarda
    # hasta un minuto en sacar al bot del canal de voz.
    def _sigterm(signum, frame):  # noqa: ARG001
        log.info("SIGTERM recibido: cerrando elegante (desconectando la voz)...")
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _sigterm)

    try:
        bot.run(token, log_handler=None)
    except KeyboardInterrupt:
        pass
    log.info("Bot detenido limpiamente.")


if __name__ == "__main__":
    main()
