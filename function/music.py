import asyncio
import re

import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp


YTDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch1",
    "source_address": "0.0.0.0",
    "extract_flat": False,
}

FFMPEG_BEFORE_OPTS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTS = "-vn"

URL_RE = re.compile(r"^https?://", re.I)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)

    def _log(self, text: str):
        print(f"[MUSIC] {text}", flush=True)

    def _normalize(self, text: str) -> str:
        return (text or "").strip().lower()

    def _is_url(self, text: str) -> bool:
        return bool(URL_RE.match((text or "").strip()))

    def _is_generator_channel(self, channel) -> bool:
        if channel is None:
            return False

        name = self._normalize(channel.name)
        patterns = [
            "tao voice",
            "tạo voice",
            "tao-voice",
            "tạo-voice",
            "tao voice rieng",
            "tạo voice riêng",
            "tao-voice-rieng",
            "tạo-voice-riêng",
            "join to create",
            "create voice",
        ]
        return any(p in name for p in patterns)

    async def _get_user_voice_channel(self, member: discord.Member):
        if not member.voice or not member.voice.channel:
            return None
        return member.voice.channel

    async def _resolve_real_target_channel(self, member: discord.Member):
        channel = await self._get_user_voice_channel(member)
        if channel is None:
            self._log("User is not in voice")
            return None

        self._log(f"Initial user channel: {channel.name}")

        if not self._is_generator_channel(channel):
            return channel

        self._log(f"Generator channel detected: {channel.name} -> waiting for real room")
        await asyncio.sleep(2.5)

        refreshed_member = member.guild.get_member(member.id)
        if refreshed_member is None:
            self._log("Cannot refresh member")
            return None

        new_channel = await self._get_user_voice_channel(refreshed_member)
        if new_channel is None:
            self._log("User left voice while waiting")
            return None

        self._log(f"Channel after wait: {new_channel.name}")

        if self._is_generator_channel(new_channel):
            self._log("Still in generator channel, refusing to join")
            return None

        return new_channel

    async def _ensure_connected(self, guild: discord.Guild, channel: discord.VoiceChannel):
        vc = guild.voice_client

        if vc is not None:
            try:
                if vc.is_connected() and vc.channel is not None:
                    if vc.channel.id != channel.id:
                        self._log(f"Move from {vc.channel.name} -> {channel.name} | guild={guild.name}")
                        await vc.move_to(channel)
                    else:
                        self._log(f"Already connected at {channel.name} | guild={guild.name}")
                    return vc

                self._log(f"Cleaning stale voice client | guild={guild.name}")
                try:
                    await vc.disconnect(force=True)
                except Exception:
                    pass
                try:
                    vc.cleanup()
                except Exception:
                    pass
            except Exception as e:
                self._log(f"Voice client pre-check failed | guild={guild.name} | error={e}")

        self._log(f"Connecting to {channel.name} | guild={guild.name}")

        try:
            vc = await channel.connect(
                timeout=20.0,
                reconnect=False,
                self_deaf=True,
                self_mute=False,
            )
        except asyncio.TimeoutError:
            self._log(f"Voice connect timeout | guild={guild.name}")
            stale = guild.voice_client
            if stale is not None:
                try:
                    await stale.disconnect(force=True)
                except Exception:
                    pass
                try:
                    stale.cleanup()
                except Exception:
                    pass
            raise RuntimeError(
                "Kết nối voice bị timeout. Thường là do mạng/firewall/VPN hoặc voice handshake bị lỗi."
            )

        self._log(f"Connected to {channel.name} | guild={guild.name}")
        return vc

    async def _extract_info(self, query: str):
        loop = asyncio.get_running_loop()
        search_text = query if self._is_url(query) else f"ytsearch1:{query}"

        def run():
            return self.ytdl.extract_info(search_text, download=False)

        data = await loop.run_in_executor(None, run)

        if data is None:
            raise RuntimeError("Không lấy được dữ liệu từ YouTube.")

        if "entries" in data:
            entries = [e for e in data["entries"] if e]
            if not entries:
                raise RuntimeError("Không tìm thấy bài hát phù hợp.")
            data = entries[0]

        return data

    def _build_source(self, stream_url: str):
        return discord.FFmpegOpusAudio(
            stream_url,
            before_options=FFMPEG_BEFORE_OPTS,
            options=FFMPEG_OPTS,
        )

    async def play_internal(self, message, query: str):
        if not message or not isinstance(message.author, discord.Member):
            return "❌ Không xác định được người gọi."

        channel = await self._resolve_real_target_channel(message.author)
        if not channel:
            return "❌ Bạn đang đứng ở kênh tạo voice hoặc chưa vào phòng voice thật. Hãy vào room voice thật rồi thử lại."

        if not query.strip():
            return "❌ Bạn chưa nhập tên bài hoặc link YouTube."

        vc = await self._ensure_connected(message.guild, channel)

        info = await self._extract_info(query)
        title = info.get("title") or "Không rõ tiêu đề"
        webpage_url = info.get("webpage_url") or query
        stream_url = info.get("url")

        if not stream_url:
            raise RuntimeError("Không lấy được audio stream URL.")

        if vc.is_playing() or vc.is_paused():
            vc.stop()

        source = self._build_source(stream_url)

        self._log(f"Play: {title}")
        vc.play(
            source,
            after=lambda err: print(f"[MUSIC] Playback error: {err}", flush=True) if err else None,
        )

        return f"🎵 Đang phát: **{title}**\n{webpage_url}"

    async def play_music_internal(self, *, message=None, query: str = ""):
        if not message:
            return "❌ Không xác định được người gọi."
        if not query.strip():
            return "❌ Bạn chưa nhập tên bài hoặc link YouTube."
        return await self.play_internal(message, query)

    async def stop_music_internal(self, *, message=None):
        if not message or not message.guild:
            return "❌ Không xác định được server."

        vc = message.guild.voice_client
        if not vc or not vc.is_connected():
            return "❌ Bot chưa ở trong voice."

        if vc.is_playing() or vc.is_paused():
            vc.stop()
            return "⏹️ Đã dừng nhạc."
        return "❌ Hiện không có bài nào đang phát."

    async def pause_music_internal(self, *, message=None):
        if not message or not message.guild:
            return "❌ Không xác định được server."

        vc = message.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            return "⏸️ Đã tạm dừng nhạc."
        return "❌ Không có bài nào đang phát."

    async def resume_music_internal(self, *, message=None):
        if not message or not message.guild:
            return "❌ Không xác định được server."

        vc = message.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            return "▶️ Đã phát tiếp."
        return "❌ Không có bài nào đang tạm dừng."

    async def skip_music_internal(self, *, message=None):
        if not message or not message.guild:
            return "❌ Không xác định được server."

        vc = message.guild.voice_client
        if not vc or not vc.is_connected():
            return "❌ Bot chưa ở trong voice."

        if vc.is_playing() or vc.is_paused():
            vc.stop()
            return "⏭️ Đã skip bài hiện tại."
        return "❌ Không có bài nào để skip."

    @commands.command(name="play")
    async def play_prefix(self, ctx: commands.Context, *, query: str):
        try:
            text = await self.play_internal(ctx.message, query)
            await ctx.reply(text)
        except Exception as e:
            await ctx.reply(f"❌ Lỗi play: `{e}`")

    @commands.command(name="stop")
    async def stop_prefix(self, ctx: commands.Context):
        text = await self.stop_music_internal(message=ctx.message)
        await ctx.reply(text)

    @commands.command(name="pause")
    async def pause_prefix(self, ctx: commands.Context):
        text = await self.pause_music_internal(message=ctx.message)
        await ctx.reply(text)

    @commands.command(name="resume")
    async def resume_prefix(self, ctx: commands.Context):
        text = await self.resume_music_internal(message=ctx.message)
        await ctx.reply(text)

    @commands.command(name="skip")
    async def skip_prefix(self, ctx: commands.Context):
        text = await self.skip_music_internal(message=ctx.message)
        await ctx.reply(text)

    @app_commands.command(name="play", description="Phát nhạc YouTube bằng tên bài hoặc link")
    async def play_slash(self, interaction: discord.Interaction, query: str):
        if interaction.guild is None:
            await interaction.response.send_message("❌ Chỉ dùng trong server.", ephemeral=True)
            return

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Không xác định được người dùng.", ephemeral=True)
            return

        await interaction.response.defer()

        fake_message = type("FakeMessage", (), {})()
        fake_message.author = interaction.user
        fake_message.guild = interaction.guild
        fake_message.channel = interaction.channel
        fake_message.content = query

        try:
            text = await self.play_internal(fake_message, query)
            await interaction.followup.send(text)
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi play: `{e}`")

    @app_commands.command(name="stop_music", description="Dừng nhạc")
    async def stop_music(self, interaction: discord.Interaction):
        fake_message = type("FakeMessage", (), {})()
        fake_message.guild = interaction.guild
        text = await self.stop_music_internal(message=fake_message)
        await interaction.response.send_message(text, ephemeral=True)

    @app_commands.command(name="pause_music", description="Tạm dừng nhạc")
    async def pause_music(self, interaction: discord.Interaction):
        fake_message = type("FakeMessage", (), {})()
        fake_message.guild = interaction.guild
        text = await self.pause_music_internal(message=fake_message)
        await interaction.response.send_message(text, ephemeral=True)

    @app_commands.command(name="resume_music", description="Phát tiếp nhạc")
    async def resume_music(self, interaction: discord.Interaction):
        fake_message = type("FakeMessage", (), {})()
        fake_message.guild = interaction.guild
        text = await self.resume_music_internal(message=fake_message)
        await interaction.response.send_message(text, ephemeral=True)

    @app_commands.command(name="skip_music", description="Skip bài hiện tại")
    async def skip_music(self, interaction: discord.Interaction):
        fake_message = type("FakeMessage", (), {})()
        fake_message.guild = interaction.guild
        text = await self.skip_music_internal(message=fake_message)
        await interaction.response.send_message(text, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Music(bot))