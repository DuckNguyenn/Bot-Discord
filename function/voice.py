import asyncio
import os
import tempfile

import discord
from discord import app_commands
from discord.ext import commands

try:
    from gtts import gTTS
except Exception:
    gTTS = None


class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _log(self, text: str):
        print(f"[VOICE V2] {text}", flush=True)

    def _normalize(self, text: str) -> str:
        return (text or "").strip().lower()

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

    async def ensure_connected(self, guild: discord.Guild, channel: discord.VoiceChannel):
        vc = guild.voice_client

        # Nếu có client cũ nhưng đang lỗi nửa sống nửa chết thì dọn nó trước
        if vc is not None:
            try:
                if vc.is_connected() and vc.channel is not None:
                    if vc.channel.id != channel.id:
                        self._log(f"Move from {vc.channel.name} -> {channel.name} | guild={guild.name}")
                        await vc.move_to(channel)
                    else:
                        self._log(f"Already connected at {channel.name} | guild={guild.name}")
                    return vc

                # client tồn tại nhưng không connected ổn
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

    async def leave_voice(self, guild: discord.Guild):
        vc = guild.voice_client
        if vc and vc.is_connected():
            self._log(f"Disconnecting from guild={guild.name}")
            await vc.disconnect(force=True)
            return True
        return False

    async def speak_text(self, guild: discord.Guild, text: str):
        if not gTTS:
            raise RuntimeError("Thiếu gTTS. Cài: pip install gTTS")

        vc = guild.voice_client
        if not vc or not vc.is_connected():
            raise RuntimeError("Bot chưa ở trong voice")

        if vc.is_playing():
            vc.stop()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            temp_path = tmp.name

        try:
            self._log(f"TTS generating | guild={guild.name} | text={text[:80]}")
            gTTS(text=text, lang="vi").save(temp_path)

            source = discord.FFmpegPCMAudio(temp_path)
            done = asyncio.Event()

            def after_play(err):
                if err:
                    print(f"[VOICE V2] Playback error: {err}", flush=True)
                done.set()

            vc.play(source, after=after_play)
            await done.wait()
            self._log(f"TTS done | guild={guild.name}")
        finally:
            try:
                os.remove(temp_path)
            except Exception:
                pass

    async def voice_join_internal(self, *, message=None):
        if not message or not isinstance(message.author, discord.Member):
            return "❌ Không xác định được người gọi."

        channel = await self._resolve_real_target_channel(message.author)
        if not channel:
            return "❌ Bạn đang đứng ở kênh tạo voice hoặc chưa vào phòng voice thật. Hãy vào room voice thật rồi thử lại."

        await self.ensure_connected(message.guild, channel)
        return f"✅ Đã vào voice: **{channel.name}**"

    async def voice_leave_internal(self, *, message=None):
        if not message:
            return "❌ Không xác định được server."

        ok = await self.leave_voice(message.guild)
        if ok:
            return "👋 Đã rời voice."
        return "❌ Bot chưa ở trong voice."

    async def voice_say_internal(self, *, message=None, text: str = ""):
        if not message or not isinstance(message.author, discord.Member):
            return "❌ Không xác định được người gọi."

        if not text.strip():
            return "❌ Bạn chưa nhập nội dung để nói."

        channel = await self._resolve_real_target_channel(message.author)
        if not channel:
            return "❌ Bạn đang đứng ở kênh tạo voice hoặc chưa vào phòng voice thật. Hãy vào room voice thật rồi thử lại."

        await self.ensure_connected(message.guild, channel)
        await self.speak_text(message.guild, text.strip())
        return f"🗣️ Đã nói: `{text[:100]}`"

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not self.bot.user or member.id != self.bot.user.id:
            return

        guild = member.guild
        before_name = before.channel.name if before.channel else None
        after_name = after.channel.name if after.channel else None
        self._log(f"State update | guild={guild.name} | before={before_name} | after={after_name}")

    @app_commands.command(name="voice_join", description="Cho bot vào voice")
    async def voice_join(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Không xác định được người dùng.", ephemeral=True)
            return

        channel = await self._resolve_real_target_channel(interaction.user)
        if not channel:
            await interaction.response.send_message(
                "❌ Bạn đang đứng ở kênh tạo voice hoặc chưa vào phòng voice thật. Hãy vào room voice thật rồi thử lại.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        await self.ensure_connected(interaction.guild, channel)
        await interaction.followup.send(f"✅ Đã vào voice: **{channel.name}**", ephemeral=True)

    @app_commands.command(name="voice_leave", description="Cho bot rời voice")
    async def voice_leave(self, interaction: discord.Interaction):
        ok = await self.leave_voice(interaction.guild)
        if ok:
            await interaction.response.send_message("👋 Đã rời voice.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Bot chưa ở trong voice.", ephemeral=True)

    @app_commands.command(name="voice_say", description="Bot nói bằng giọng Google")
    async def voice_say(self, interaction: discord.Interaction, text: str):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Không xác định được người dùng.", ephemeral=True)
            return

        channel = await self._resolve_real_target_channel(interaction.user)
        if not channel:
            await interaction.response.send_message(
                "❌ Bạn đang đứng ở kênh tạo voice hoặc chưa vào phòng voice thật. Hãy vào room voice thật rồi thử lại.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await self.ensure_connected(interaction.guild, channel)
            await self.speak_text(interaction.guild, text)
            await interaction.followup.send("✅ Đã nói xong.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi voice: `{e}`", ephemeral=True)

    @commands.command(name="joinvc")
    async def joinvc(self, ctx: commands.Context):
        if not isinstance(ctx.author, discord.Member):
            await ctx.reply("❌ Không xác định được người dùng.")
            return

        channel = await self._resolve_real_target_channel(ctx.author)
        if not channel:
            await ctx.reply("❌ Bạn đang đứng ở kênh tạo voice hoặc chưa vào phòng voice thật. Hãy vào room voice thật rồi thử lại.")
            return

        await self.ensure_connected(ctx.guild, channel)
        await ctx.reply(f"✅ Đã vào voice: **{channel.name}**")

    @commands.command(name="leavevc")
    async def leavevc(self, ctx: commands.Context):
        ok = await self.leave_voice(ctx.guild)
        if ok:
            await ctx.reply("👋 Đã rời voice.")
        else:
            await ctx.reply("❌ Bot chưa ở trong voice.")

    @commands.command(name="say", aliases=["tts", "speak"])
    async def say(self, ctx: commands.Context, *, text: str):
        if not isinstance(ctx.author, discord.Member):
            await ctx.reply("❌ Không xác định được người dùng.")
            return

        channel = await self._resolve_real_target_channel(ctx.author)
        if not channel:
            await ctx.reply("❌ Bạn đang đứng ở kênh tạo voice hoặc chưa vào phòng voice thật. Hãy vào room voice thật rồi thử lại.")
            return

        try:
            await self.ensure_connected(ctx.guild, channel)
            await ctx.reply(f"🗣️ Đang nói: `{text[:80]}`")
            await self.speak_text(ctx.guild, text)
        except Exception as e:
            await ctx.reply(f"❌ Lỗi voice: `{e}`")


async def setup(bot):
    await bot.add_cog(Voice(bot))