import discord
from discord import app_commands
from discord.ext import commands
import urllib.parse
from datetime import datetime

# --- CẤU HÌNH ---
# Link gốc cho QR đầy đủ
LINK_GOC = "https://img.vietqr.io/image/TPB-00003474347-compact.png"
# Link cho QR đơn thuần (chỉ STK và Ngân hàng)
LINK_ORIGINAL = "https://image2url.com/r2/default/images/1771410367472-a2a72015-0984-4f08-b4fa-dfab1a117884.png"

TEN_CHU_TK = "Nguyen Tran Minh Duc"
STK = "00003474347" 
NGAN_HANG = "TPBank"
LOGO_BANK = "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/TPBank_Logo.svg/2560px-TPBank_Logo.svg.png"

ID_ADMIN = 1126531490793148427 
#ALLOWED_ROLES = ["Mèo béo", "Cat Shop"]

def check_quyen(interaction: discord.Interaction) -> bool:
    if interaction.user.id == ID_ADMIN:
        return True
    #if isinstance(interaction.user, discord.Member):
    #    return any(role.name in ALLOWED_ROLES for role in interaction.user.roles)
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
            description=f"Thằng nào có tiền thì... **{interaction.user.mention}**",
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
        # QR đơn thuần không truyền thêm amount và addInfo
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

    @qr.error
    @qr_original.error
    async def qr_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            embed = discord.Embed(
                title="TỪ CHỐI TRUY CẬP",
                description="Down đòi dùng bot",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(QR(bot))