import discord
from discord import app_commands
from discord.ext import commands

ID_ADMIN = 1126531490793148427 

def check_quyen(interaction: discord.Interaction) -> bool:
    # Chỉ Admin có ID này mới được dùng lệnh
    return interaction.user.id == ID_ADMIN

class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="botmessage", description="Nội dung")
    @app_commands.describe(
        noidung="Nội dung",
        hinhanh="Hình ảnh"
    ) 
    @app_commands.check(check_quyen)
    async def botmessage(self, interaction: discord.Interaction, noidung: str = None, hinhanh: discord.Attachment = None):
        # Kiểm tra nếu cả nội dung và ảnh đều trống
        if noidung is None and hinhanh is None:
            await interaction.response.send_message("Phải nhập nội dung", ephemeral=True)
            return

        # Phản hồi ẩn để tránh lỗi Interaction
        await interaction.response.send_message("ok", ephemeral=True)
        
        # Xử lý gửi ảnh nếu có
        file = None
        if hinhanh:
            # Chuyển đổi attachment từ Discord thành file để bot gửi đi
            file = await hinhanh.to_file()
        
        # Gửi tin nhắn thật vào kênh hiện tại
        # Sử dụng content=noidung để tránh lỗi nếu noidung là None
        await interaction.channel.send(content=noidung, file=file)

    @botmessage.error
    async def botmessage_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            # Giữ nguyên nội dung phản hồi cũ của bạn
            await interaction.response.send_message("Down à mà dùng?", ephemeral=True)
        else:
            # Xử lý các lỗi khác nếu chưa phản hồi
            if not interaction.response.is_done():
                await interaction.response.send_message(f"Lỗi: {error}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Chat(bot))