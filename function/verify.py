import discord
from discord import app_commands
from discord.ext import commands

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        oauth2_url = "https://discord.com/oauth2/authorize?client_id=1472462360903024823&response_type=code&redirect_uri=http%3A%2F%2Flocalhost%3A5000%2Fcallback&scope=identify+guilds.join"
        
        self.add_item(discord.ui.Button(
            label="Xác minh tại đây", 
            style=discord.ButtonStyle.link, 
            url=oauth2_url,
            emoji="🔗"
        ))

class VerifySystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup_verify", description="Gửi tin nhắn xác minh tài khoản")
    @app_commands.describe(kenh_chi_dinh="Chọn kênh để bot gửi bảng xác minh (bỏ trống sẽ gửi ở kênh hiện tại)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_verify(self, interaction: discord.Interaction, kenh_chi_dinh: discord.TextChannel = None):
        embed = discord.Embed(
            title="Xác thực tài khoản",
            description=(
                "🔸 Vui lòng ấn vào link hoặc **Nút 'Xác minh' dưới đây** để bắt đầu xác minh tài khoản.\n"
                "🔸 Việc xác minh sẽ giúp Cat's server tìm lại bạn nếu có bất cứ chuyện gì đột ngột xảy ra."
            ),
            color=discord.Color.dark_theme() # Màu tối giống ảnh mẫu
        )
        
        # Quyết định kênh gửi: Nếu bạn nhập kênh vào lệnh thì gửi kênh đó, không thì gửi ở kênh hiện tại
        target_channel = kenh_chi_dinh or interaction.channel
        
        # Gửi tin nhắn chứa Embed và View (nút bấm)
        await target_channel.send(embed=embed, view=VerifyView())
        await interaction.response.send_message(f"✅ Đã thiết lập hệ thống xác minh tại kênh {target_channel.mention}!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(VerifySystem(bot))