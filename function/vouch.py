import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

class Vouch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # LIỆT KÊ TẤT CẢ ID KÊNH BẠN MUỐN GỬI VOUCH VÀO ĐÂY
        self.VOUCH_CHANNELS = [
            1381650888652882000, 
            1394000620754833408,
            1402904210898554890
        ]

    @app_commands.command(name="vouch", description="Feedback")
    @app_commands.describe(
        noi_dung="Nội dung",
        hinh_anh="Minh chứng"
    )
    async def vouch(self, interaction: discord.Interaction, noi_dung: str, hinh_anh: discord.Attachment):
        # 1. Kiểm tra xem file gửi lên có phải là ảnh không
        if not hinh_anh.content_type or not hinh_anh.content_type.startswith("image"):
            await interaction.response.send_message("Không hợp lệ", ephemeral=True)
            return

        # Dùng defer vì gửi nhiều kênh có thể tốn hơn 3s
        await interaction.response.defer(ephemeral=True)

        # 2. Tạo Embed (Giữ nguyên y hệt bảng ban đầu của bạn)
        embed = discord.Embed(
            title="Vouch",
            description=f"**User:** {interaction.user.mention}\n**Nội dung:** {noi_dung}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.set_image(url=hinh_anh.url)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"User ID: {interaction.user.id}")

        # 3. Gửi vào tất cả các kênh trong danh sách
        success_list = []
        failed_count = 0

        for channel_id in self.VOUCH_CHANNELS:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(embed=embed)
                    success_list.append(channel.mention)
                except:
                    failed_count += 1
            else:
                failed_count += 1

        # 4. Phản hồi kết quả
        if success_list:
            mentions = ", ".join(success_list)
            await interaction.followup.send(f"Success {mentions}!", ephemeral=True)
        else:
            await interaction.followup.send(f"Failed", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Vouch(bot))