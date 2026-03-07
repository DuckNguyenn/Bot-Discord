import discord
from discord import app_commands
from discord.ext import commands
import urllib.parse
from datetime import datetime

# --- CẤU HÌNH ---
# Link gốc cho QR đầy đủ
LINK_GOC = "https://img.vietqr.io/image/TPB-00003474347-compact.png"
LINK_ORIGINAL = "https://image2url.com/r2/default/images/1771410367472-a2a72015-0984-4f08-b4fa-dfab1a117884.png"

# 👇 THÊM LINK QR MOMO CỦA BẠN VÀO ĐÂY 👇
LINK_MOMO = "https://image2url.com/r2/default/images/1772905222181-dde61035-f75d-4644-a6ad-77065fd6ec99.png" 

TEN_CHU_TK = "Nguyen Tran Minh Duc"
STK = "00003474347" 
NGAN_HANG = "TPBank"
LOGO_BANK = "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/TPBank_Logo.svg/2560px-TPBank_Logo.svg.png"

ID_ADMIN = 1126531490793148427, 917980517813608499, 1281836308376981566, 1024690715382534144, 1324752071349506091, 1109225990791630909
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

    # --- LỆNH QR ĐẦY ĐỦ (CÓ TIỀN + NỘI DUNG) ---
    @app_commands.command(name="qr", description="Qr thanh toán có số tiền và nội dung")
    @app_commands.describe(amount="Số tiền", content="Lời nhắn")
    @app_commands.check(check_quyen)
    async def qr(self, interaction: discord.Interaction, amount: int, content: str):
        content_safe = urllib.parse.quote(content, safe='')
        name_safe = urllib.parse.quote(TEN_CHU_TK, safe='')
        final_url = f"{LINK_GOC}?amount={amount}&addInfo={content_safe}&accountName={name_safe}"

        amount_fmt = f"{amount:,}".replace(',', '.')

        embed = discord.Embed(
            title="Pate cho mèo béo 🐱", 
            description=f"Thằng nào có tiền thì...",
            color=0x6f3da1, 
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=LOGO_BANK)
        embed.add_field(name="Ngân hàng", value=f"**{NGAN_HANG}**", inline=True)
        embed.add_field(name="Chủ tài khoản", value=f"**{TEN_CHU_TK.upper()}**", inline=True)
        embed.add_field(name="Số tài khoản", value=f"```yaml\n{STK}\n```", inline=False)
        embed.add_field(name="Số tiền", value=f"```fix\n{amount_fmt} VNĐ\n```", inline=True)
        embed.add_field(name="Nội dung CK", value=f"```css\n{content}\n```", inline=True)
        embed.set_image(url=final_url)
        embed.set_footer(text="Meow Meow", icon_url="https://media.tenor.com/FLfJEQ0Q8wQAAAAM/rigby-freaky.gif")
        
        await interaction.response.send_message(embed=embed)

    # --- LỆNH QR ORIGINAL (CHỈ THÔNG TIN BANK) ---
    @app_commands.command(name="qr_original", description="QR bank bth")
    @app_commands.check(check_quyen)
    async def qr_original(self, interaction: discord.Interaction):
        final_url = LINK_ORIGINAL 

        embed = discord.Embed(
            title="QR", 
            color=0x6f3da1, 
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=LOGO_BANK)
        embed.add_field(name="Ngân hàng", value=f"**{NGAN_HANG}**", inline=True)
        embed.add_field(name="Chủ tài khoản", value=f"**{TEN_CHU_TK.upper()}**", inline=True)
        embed.add_field(name="Số tài khoản", value=f"```yaml\n{STK}\n```", inline=False)
        
        embed.set_image(url=final_url)
        embed.set_footer(text="Meow Meow", icon_url="https://media.tenor.com/FLfJEQ0Q8wQAAAAM/rigby-freaky.gif")
        
        await interaction.response.send_message(embed=embed)

    # --- LỆNH MOMO ĐÃ CẤU HÌNH SẴN ---
    @app_commands.command(name="momo", description="Gửi mã QR Momo")
    @app_commands.check(check_quyen)
    async def momo(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Momo", 
            description=f"Thằng nào có tiền thì...",
            color=0xa50064, # Mã màu củ dền chuẩn của Momo
            timestamp=datetime.now()
        )
        # Gắn logo Momo nhỏ ở góc
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/vi/f/fe/MoMo_Logo.png")
        # Gắn link ảnh QR mà bạn đã cấu hình ở trên cùng
        embed.set_image(url=LINK_MOMO)
        embed.set_footer(text="Meow Meow", icon_url="https://media.tenor.com/FLfJEQ0Q8wQAAAAM/rigby-freaky.gif")
        
        await interaction.response.send_message(embed=embed)

    # --- BẮT LỖI QUYỀN HẠN ---
    @qr.error
    @qr_original.error
    @momo.error
    async def error_handler(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            embed = discord.Embed(
                title="TỪ CHỐI TRUY CẬP",
                description=f"Down đòi dùng bot\n*(ID của bạn là: `{interaction.user.id}`)*",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(QR(bot))