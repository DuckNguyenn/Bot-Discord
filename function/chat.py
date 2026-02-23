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

    @app_commands.command(name="botmessage", description="Gửi tin nhắn kèm hình ảnh qua bot")
    @app_commands.describe(
        noidung="Nội dung văn bản",
        hinhanh="Kéo thả hình ảnh vào đây"
    ) 
    @app_commands.check(check_quyen)
    async def botmessage(self, interaction: discord.Interaction, noidung: str = None, hinhanh: discord.Attachment = None):
        if noidung is None and hinhanh is None:
            await interaction.response.send_message("Phải nhập nội dung", ephemeral=True)
            return

        await interaction.response.send_message("ok", ephemeral=True)
        
        file = None
        if hinhanh:
            file = await hinhanh.to_file()
        
        await interaction.channel.send(content=noidung, file=file)

    @app_commands.command(name="svv", description="Link svv")
    @app_commands.check(check_quyen)
    async def svv(self, interaction: discord.Interaction):
        link_roblox = "https://www.roblox.com/share?code=54f7843b34b6334ab95d82efd9952a22&type=Server"
        # ephemeral=True đảm bảo chỉ người dùng lệnh mới nhìn thấy tin nhắn này
        await interaction.response.send_message(f"{link_roblox}", ephemeral=True)

    @app_commands.command(name="banggia", description="Bảng giá Cat's shop")
    async def banggia(self, interaction: discord.Interaction):
        banggia_imag = "https://image2url.com/r2/default/images/1771853325250-becfda81-7dd9-4110-a63b-4d151079f929.png"
        await interaction.response.send_message(f"{banggia_imag}")
    
    @botmessage.error
    @svv.error
    async def quyen_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("Down à mà dùng?", ephemeral=True)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"Lỗi: {error}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Chat(bot))