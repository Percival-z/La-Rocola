"""Cog con los comandos de música: /play /pause /resume /stop /skip /queue."""

from __future__ import annotations

import logging
import random

import discord
import wavelink
import yarl
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("bot.music")


def _is_url(query: str) -> bool:
    try:
        return bool(yarl.URL(query).host)
    except Exception:
        return False


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # guild_id -> channel_id donde anunciar "reproduciendo ahora"
        self._announce: dict[int, int] = {}

    # ------------------------------------------------------------------ utilidades

    def _player(self, interaction: discord.Interaction) -> wavelink.Player | None:
        """Player conectado en el servidor del interaction, si existe."""
        guild = interaction.guild
        if guild is None:
            return None
        vc = guild.voice_client
        if isinstance(vc, wavelink.Player) and vc.connected:
            return vc
        return None

    async def _player_for_play(self, interaction: discord.Interaction) -> wavelink.Player | None:
        """Devuelve el player existente o conecta al canal de voz del usuario.

        Si el bot ya está en un canal distinto al del usuario, devuelve None.
        """
        player = self._player(interaction)
        user_voice = interaction.user.voice.channel if interaction.user.voice else None

        if player is not None:
            if user_voice is not None and player.channel is not None:
                if user_voice.id != player.channel.id:
                    return None  # bot en otro canal
            return player

        if user_voice is None:
            return None
        try:
            return await user_voice.channel.connect(cls=wavelink.Player)
        except (discord.ClientException, discord.HTTPException, OSError):
            log.exception("No se pudo conectar a %s", user_voice.name)
            return None

    async def _search(self, query: str):
        """Busca en Lavalink. URLs tal cual; texto con spsearch: y fallback ytmsearch:."""
        if _is_url(query):
            return await wavelink.Playable.search(query)
        for source in ("spsearch:", "ytmsearch:"):
            try:
                results = await wavelink.Playable.search(query, source=source)
            except wavelink.LavalinkLoadException:
                continue
            if results:
                return results
        return None

    async def _advance(self, player: wavelink.Player) -> None:
        """Saca el siguiente de la cola y lo reproduce (auto-advance manual)."""
        if player.queue.is_empty:  # is_empty es property en Wavelink 3.x
            return
        try:
            next_track = player.queue.get()
        except wavelink.QueueEmpty:
            return
        await player.play(next_track)

    # ------------------------------------------------------------------ eventos

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload) -> None:
        if payload.reason == "replaced":
            return
        try:
            await self._advance(payload.player)
        except Exception:
            log.exception("Error avanzando la cola")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        track = payload.track
        if track is None:
            return
        channel_id = self._announce.get(payload.player.guild.id)
        channel = self.bot.get_channel(channel_id) if channel_id else None
        if channel is None:
            return
        embed = discord.Embed(
            title="▶️ Reproduciendo ahora",
            description=f"[{track.title}]({track.uri})" if track.uri else track.title,
            color=discord.Color.blurple(),
        )
        if track.artwork:
            embed.set_thumbnail(url=track.artwork)
        if track.author:
            embed.set_footer(text=track.author)
        try:
            # silent=True: mensaje visible en el canal pero sin notificación
            # push/escritorio (flag suppress_notifications de Discord).
            await channel.send(embed=embed, silent=True)
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload: wavelink.TrackExceptionEventPayload) -> None:
        exc = payload.exception or {}
        log.error("Error de track: %s / %s", exc.get("message"), exc.get("cause"))

    # ------------------------------------------------------------------ comandos

    @app_commands.command(name="play", description="Reproduce una canción o una playlist (Spotify / YouTube Music)")
    @app_commands.describe(
        query="Nombre de la canción o enlace de Spotify / YouTube Music",
        shuffle="Baraja el orden de la playlist antes de reproducir",
    )
    async def play(self, interaction: discord.Interaction, query: str, shuffle: bool = False) -> None:
        await interaction.response.defer()

        player = await self._player_for_play(interaction)
        if player is None:
            await interaction.followup.send(
                "❌ Entra a un canal de voz (y al mismo canal que el bot) antes de usar /play."
            )
            return

        try:
            results = await self._search(query)
        except wavelink.LavalinkLoadException as exc:
            await interaction.followup.send(f"❌ Lavalink devolvió un error: `{exc}`")
            return

        if not results:
            await interaction.followup.send("❌ No encontré nada con eso. Prueba con otro nombre o enlace.")
            return

        if isinstance(results, wavelink.Playlist):
            tracks = list(results.tracks)
            title = results.name or "Playlist"
            url = results.url
            artwork = results.artwork
            is_playlist = True
        else:
            tracks = list(results)
            title = tracks[0].title if tracks else "?"
            url = tracks[0].uri if tracks else None
            artwork = tracks[0].artwork if tracks else None
            is_playlist = False

        if not tracks:
            await interaction.followup.send("❌ No hay pistas en el resultado.")
            return

        if shuffle:
            random.shuffle(tracks)

        for track in tracks:
            try:
                track.extras["requester_id"] = interaction.user.id
            except Exception:
                pass

        idle = player.current is None
        for track in tracks:
            player.queue.put(track)

        if idle:
            await self._advance(player)

        if interaction.guild is not None and interaction.channel is not None:
            self._announce[interaction.guild.id] = interaction.channel.id

        if is_playlist:
            desc = f"Añadida a la cola: **{len(tracks)}** temas" + (" (mezcladas 🎲)" if shuffle else "")
            embed = discord.Embed(title=f"📋 {title}", url=url, description=desc, color=discord.Color.green())
        else:
            status = "Reproduciendo ahora" if idle else "Añadida a la cola"
            extra = f" ×{len(tracks)}" if len(tracks) > 1 else ""
            embed = discord.Embed(
                title=f"🎵 {title}{extra}",
                url=url,
                description=f"{status}." + (" (mezcladas 🎲)" if shuffle and len(tracks) > 1 else ""),
                color=discord.Color.green(),
            )
        if artwork:
            embed.set_thumbnail(url=artwork)
        # silent=True: confirmación visible sin disparar notificaciones.
        await interaction.followup.send(embed=embed, silent=True)

    @app_commands.command(name="pause", description="Pausa la reproducción")
    async def pause(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        if player is None or player.current is None:
            await interaction.response.send_message("❌ No hay nada reproduciéndose.", ephemeral=True)
            return
        await player.pause(True)
        await interaction.response.send_message("⏸️ Pausado.", ephemeral=True)

    @app_commands.command(name="resume", description="Reanuda la reproducción")
    async def resume(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        if player is None or player.current is None:
            await interaction.response.send_message("❌ No hay nada pausado.", ephemeral=True)
            return
        await player.pause(False)
        await interaction.response.send_message("▶️ Reanudado.", ephemeral=True)

    @app_commands.command(name="stop", description="Detiene la reproducción y vacía la cola")
    async def stop(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        if player is None:
            await interaction.response.send_message("❌ No estoy en un canal de voz.", ephemeral=True)
            return
        player.queue.clear()
        await player.stop()
        await interaction.response.send_message("⏹️ Detenido. Cola vacía.", ephemeral=True)

    @app_commands.command(name="skip", description="Salta a la siguiente canción")
    async def skip(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        if player is None or player.current is None:
            await interaction.response.send_message("❌ No hay nada que saltar.", ephemeral=True)
            return
        await player.skip()
        await interaction.response.send_message("⏭️ Saltada.", ephemeral=True)

    @app_commands.command(name="queue", description="Muestra la cola de reproducción")
    async def queue(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        if player is None:
            await interaction.response.send_message("❌ No estoy en un canal de voz.", ephemeral=True)
            return

        items = list(player.queue)
        embed = discord.Embed(title=" Cola de reproducción", color=discord.Color.blurple())

        if player.current is not None:
            embed.add_field(
                name="Ahora",
                value=f"[{player.current.title}]({player.current.uri})" if player.current.uri else player.current.title,
                inline=False,
            )

        if not items:
            embed.description = "La cola está vacía."
        else:
            lines = []
            for i, track in enumerate(items[:10], start=1):
                title = track.title or "?"
                lines.append(f"`{i}.` [{title}]({track.uri})" if track.uri else f"`{i}.` {title}")
            if len(items) > 10:
                lines.append(f"\n… y **{len(items) - 10}** más.")
            embed.description = "\n".join(lines)

        embed.set_footer(text=f"{len(items)} en cola")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))
