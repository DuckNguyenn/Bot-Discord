import urllib.parse
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

LINK_GOC = "https://img.vietqr.io/image/TPB-00003474347-compact.png"
LINK_ORIGINAL = "https://image2url.com/r2/default/images/1771410367472-a2a72015-0984-4f08-b4fa-dfab1a117884.png"
LINK_MOMO = "https://image2url.com/r2/default/images/1772905222181-dde61035-f75d-4644-a6ad-77065fd6ec99.png"

TEN_CHU_TK = "Nguyen Tran Minh Duc"
STK = "00003474347"
NGAN_HANG = "TPBank"
LOGO_BANK = "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/TPBank_Logo.svg/2560px-TPBank_Logo.svg.png"

ID_ADMIN = (
    1126531490793148427,
    917980517813608499,
    1281836308376981566,
    1024690715382534144,
    1324752071349506091,
    1109225990791630909,
)
ALLOWED_ROLES = ["Mèo béo", "[Cat Shop] - Supporter"]


def check_quyen(interaction: discord.Interaction) -> bool:
    if interaction.user.id in ID_ADMIN:
        return True
    if isinstance(interaction.user, discord.Member):
        return any(role.name in ALLOWED_ROLES for role in interaction.user.roles)
    return False


class QR(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _build_qr_embed(self, amount: Optional[int] = None, content: Optional[str] = None) -> discord.Embed:
        if amount is None:
            embed = discord.Embed(title="QR", color=0x6F3DA1, timestamp=datetime.now())
            embed.set_thumbnail(url=LOGO_BANK)
            embed.add_field(name="Ngân hàng", value=f"**{NGAN_HANG}**", inline=True)
            embed.add_field(name="Chủ tài khoản", value=f"**{TEN_CHU_TK.upper()}**", inline=True)
            embed.add_field(name="Số tài khoản", value=f"```yaml\n{STK}\n```", inline=False)
            embed.set_image(url=LINK_ORIGINAL)
            embed.set_footer(text="Meow Meow", icon_url="https://media.tenor.com/FLfJEQ0Q8wQAAAAM/rigby-freaky.gif")
            return embed

        clean_content = (content or "").strip()
        amount_fmt = f"{amount:,}".replace(",", ".")
        name_safe = urllib.parse.quote(TEN_CHU_TK, safe="")
        content_safe = urllib.parse.quote(clean_content, safe="")
        final_url = f"{LINK_GOC}?amount={amount}&addInfo={content_safe}&accountName={name_safe}"

        embed = discord.Embed(
            title="Pate cho mèo béo 🐱",
            description="Thằng nào có tiền thì...",
            color=0x6F3DA1,
            timestamp=datetime.now(),
        )
        embed.set_thumbnail(url=LOGO_BANK)
        embed.add_field(name="Ngân hàng", value=f"**{NGAN_HANG}**", inline=True)
        embed.add_field(name="Chủ tài khoản", value=f"**{TEN_CHU_TK.upper()}**", inline=True)
        embed.add_field(name="Số tài khoản", value=f"```yaml\n{STK}\n```", inline=False)
        embed.add_field(name="Số tiền", value=f"```fix\n{amount_fmt} VNĐ\n```", inline=True)
        embed.add_field(name="Nội dung CK", value=f"```css\n{clean_content or '-'}\n```", inline=True)
        embed.set_image(url=final_url)
        embed.set_footer(text="Meow Meow", icon_url="https://media.tenor.com/FLfJEQ0Q8wQAAAAM/rigby-freaky.gif")
        return embed

    async def send_qr_internal(
        self,
        *,
        message: Optional[discord.Message] = None,
        channel: Optional[discord.abc.Messageable] = None,
        interaction: Optional[discord.Interaction] = None,
        amount: Optional[int] = None,
        content: Optional[str] = None,
        original: bool = False,
        reply: bool = True,
    ):
        if original:
            amount = None
            content = None

        embed = self._build_qr_embed(amount=amount, content=content)

        if interaction is not None:
            if interaction.response.is_done():
                return await interaction.followup.send(embed=embed)
            return await interaction.response.send_message(embed=embed)

        target_channel = channel or (message.channel if message else None)
        if target_channel is None:
            raise ValueError("Thiếu channel để gửi QR")

        if message is not None and reply:
            return await message.reply(embed=embed, mention_author=False)
        return await target_channel.send(embed=embed)

    async def run_qr_internal(
        self,
        *,
        message: Optional[discord.Message] = None,
        amount: Optional[int] = None,
        note: Optional[str] = None,
        content: Optional[str] = None,
        original: bool = False,
    ):
        qr_content = content if content is not None else note
        return await self.send_qr_internal(
            message=message,
            amount=amount,
            content=qr_content,
            original=original,
            reply=True,
        )

    async def qr_internal(self, **kwargs):
        return await self.run_qr_internal(**kwargs)

    async def send_momo_internal(
        self,
        *,
        message: Optional[discord.Message] = None,
        channel: Optional[discord.abc.Messageable] = None,
        interaction: Optional[discord.Interaction] = None,
        reply: bool = True,
    ):
        embed = discord.Embed(
            title="Momo",
            description="Thằng nào có tiền thì...",
            color=0xA50064,
            timestamp=datetime.now(),
        )
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/vi/f/fe/MoMo_Logo.png")
        embed.set_image(url=LINK_MOMO)
        embed.set_footer(text="Meow Meow", icon_url="https://media.tenor.com/FLfJEQ0Q8wQAAAAM/rigby-freaky.gif")

        if interaction is not None:
            if interaction.response.is_done():
                return await interaction.followup.send(embed=embed)
            return await interaction.response.send_message(embed=embed)

        target_channel = channel or (message.channel if message else None)
        if target_channel is None:
            raise ValueError("Thiếu channel để gửi Momo")

        if message is not None and reply:
            return await message.reply(embed=embed, mention_author=False)
        return await target_channel.send(embed=embed)

    @app_commands.command(name="qr", description="Qr thanh toán có số tiền và nội dung")
    @app_commands.describe(amount="Số tiền", content="Lời nhắn, có thể bỏ trống")
    @app_commands.check(check_quyen)
    async def qr(self, interaction: discord.Interaction, amount: int, content: Optional[str] = None):
        await self.send_qr_internal(interaction=interaction, amount=amount, content=content)

    @app_commands.command(name="qr_original", description="QR bank bth")
    @app_commands.check(check_quyen)
    async def qr_original(self, interaction: discord.Interaction):
        await self.send_qr_internal(interaction=interaction, original=True)

    @app_commands.command(name="momo", description="Gửi mã QR Momo")
    @app_commands.check(check_quyen)
    async def momo(self, interaction: discord.Interaction):
        await self.send_momo_internal(interaction=interaction)

    @qr.error
    @qr_original.error
    @momo.error
    async def error_handler(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            embed = discord.Embed(
                title="TỪ CHỐI TRUY CẬP",
                description=f"Down đòi dùng bot\n*(ID của bạn là: `{interaction.user.id}`)*",
                color=discord.Color.red(),
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            text = f"❌ Lỗi QR: `{error}`"
            if interaction.response.is_done():
                await interaction.followup.send(text, ephemeral=True)
            else:
                await interaction.response.send_message(text, ephemeral=True)


async def setup(bot):
    await bot.add_cog(QR(bot))
