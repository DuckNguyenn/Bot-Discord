import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

class Vouch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Thay ID_KENH_VOUCH bằng ID kênh bạn muốn tin nhắn gửi vào
        self.ID_KENH_VOUCH = 1381650888652882000 

    @app_commands.command(name="vouch", description="Đánh giá sản phẩm dịch vụ")
    @app_commands.describe(
        san_pham="Tên sản phẩm bạn đã mua",
        danh_gia="Số sao đánh giá (1-5)",
        hinh_anh="Hình ảnh minh chứng giao dịch"
    )
    async def vouch(
        self, 
        interaction: discord.Interaction, 
        san_pham: str, 
        danh_gia: app_commands.Range[int, 1, 5], 
        hinh_anh: discord.Attachment
    ):
        # Kiểm tra nếu file tải lên không phải là ảnh
        if not hinh_anh.content_type.startswith("image"):
            await interaction.response.send_message("File đính kèm phải là hình ảnh!", ephemeral=True)
            return

        # Phản hồi ẩn để xác nhận đã nhận lệnh
        await interaction.response.send_message("Đã gửi đánh giá", ephemeral=True)

        # Lấy channel chỉ định theo ID
        target_channel = self.bot.get_channel(self.ID_KENH_VOUCH)
        
        # Nếu không tìm thấy channel (sai ID hoặc bot không có quyền xem), gửi tại channel hiện tại
        if target_channel is None:
            target_channel = interaction.channel

        # Tạo chuỗi sao dựa trên số sao người dùng nhập
        stars = "⭐" * danh_gia

        # Tạo Embed hiển thị đánh giá (Giữ nguyên nội dung của bạn)
        embed = discord.Embed(
            title="Vouch/Tus ut",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.add_field(name="User: ", value=interaction.user.mention, inline=True)
        embed.add_field(name="Nội dung: ", value=san_pham, inline=True)
        embed.add_field(name="Đánh giá", value=f"{stars} ({danh_gia}/5)", inline=False)
        
        embed.set_image(url=hinh_anh.url)
        embed.set_footer(
            text="Cảm ơn bạn đã tin tưởng sử dụng dịch vụ!", 
            icon_url=interaction.user.display_avatar.url
        )

        # Gửi tin nhắn đánh giá vào kênh chỉ định
        message = await target_channel.send(embed=embed)
        
        # Thêm emoji tích xanh dưới tin nhắn
        await message.add_reaction("✅")

async def setup(bot):
    await bot.add_cog(Vouch(bot))