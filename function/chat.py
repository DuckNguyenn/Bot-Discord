import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import asyncio

# --- CẤU HÌNH DANH SÁCH QUYỀN HẠN ---
LIST_ID_ADMINS = [1126531490793148427] 
LIST_ID_ROLES = [] 

def check_quyen(interaction: discord.Interaction) -> bool:
    if interaction.user.id in LIST_ID_ADMINS:
        return True
    user_role_ids = [role.id for role in interaction.user.roles]
    return any(role_id in LIST_ID_ROLES for role_id in user_role_ids)

# --- CLASS GIAO DIỆN MENU CHỌN SERVER ---
class RaobaiSelect(discord.ui.Select):
    def __init__(self, bot, db_path, img_cat_shop, options):
        super().__init__(
            placeholder="Nhấp để xem danh sách server...",
            min_values=1,
            max_values=1,
            options=options
        )
        self.bot = bot
        self.db_path = db_path
        self.img_cat_shop = img_cat_shop

    async def callback(self, interaction: discord.Interaction):
        # Trì hoãn phản hồi để bot có thời gian đi gửi tin nhắn
        await interaction.response.defer(ephemeral=True)
        selected_value = self.values[0]
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        if selected_value == "ALL":
            # Gửi tất cả
            c.execute('SELECT * FROM raobai_channels')
        else:
            # Gửi 1 server cụ thể
            s_id = int(selected_value)
            c.execute('SELECT * FROM raobai_channels WHERE guild_id = ?', (s_id,))
            
        rows = c.fetchall()
        conn.close()

        success = 0
        report = []
        
        for g_id, c_id, g_name in rows:
            channel = self.bot.get_channel(c_id)
            if channel:
                try:
                    await channel.send(self.img_cat_shop)
                    success += 1
                    report.append(f"✅ `{g_name}`")
                    await asyncio.sleep(1) # Chống spam rate limit
                except:
                    report.append(f"❌ `{g_name}` (Lỗi quyền gửi bài)")
            else:
                report.append(f"❓ `{g_name}` (Không tìm thấy kênh)")

        result_msg = "**Kết quả rao bài:**\n" + "\n".join(report)
        await interaction.followup.send(f"{result_msg}\n\nThành công: **{success}/{len(rows)}**", ephemeral=True)

class RaobaiView(discord.ui.View):
    def __init__(self, bot, db_path, img_cat_shop, options):
        super().__init__(timeout=120) # Bảng menu sẽ vô hiệu sau 2 phút
        self.add_item(RaobaiSelect(bot, db_path, img_cat_shop, options))


class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'raobai_config.db'
        self.img_cat_shop = "https://image2url.com/r2/default/images/1772535296937-6abf7344-2758-4427-9926-506918c54c23.png"
        self.init_db()
        
        self.auto_responses = {
            "MH": "https://image2url.com/r2/default/images/1772188399025-059f4532-b46c-4341-a2f3-44cac9212ec6.png",
            "cat shop": self.img_cat_shop,
            "qr": "https://image2url.com/r2/default/images/1771410367472-a2a72015-0984-4f08-b4fa-dfab1a117884.png",
            "toi xin hua": "Trong trường hợp nhóm này bị điều tra bởi các cơ quan trực thuộc bộ công an (hoặc các tổ chức chính trị tương tự phục vụ cho nhà nước CHXHCNVN), tôi khẳng định mình không liên quan tới nhóm hoặc những cá nhân khác trong nhóm này. Tôi không rõ tại sao mình lại có mặt ở đây vào thời điểm này, có lẽ tài khoản của tôi đã được thêm bởi một bên thứ ba. Tôi cũng xin khẳng định rằng mình không hề giúp sức cho những hành động chống phá Đảng và nhà nước của các thành viên trong nhóm này.",
            "hoang luan 40k": "https://image2url.com/r2/default/images/1772295505216-f8e6d11a-b1fd-4cb8-abb1-b018a933664a.png",
            "momo": "https://image2url.com/r2/default/images/1772905222181-dde61035-f75d-4644-a6ad-77065fd6ec99.png"
        }

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS raobai_channels 
                     (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, guild_name TEXT)''')
        conn.commit()
        conn.close()

    # --- LỆNH CONFIG (GIỮ NGUYÊN) ---
    @app_commands.command(name="config_raobai", description="Cấu hình rao bài bằng ID Server và ID Kênh")
    @app_commands.describe(server_id="Nhập ID của Server", channel_id="Nhập ID của Kênh chat")
    @app_commands.check(check_quyen)
    async def config_raobai(self, interaction: discord.Interaction, server_id: str, channel_id: str):
        try:
            s_id = int(server_id)
            c_id = int(channel_id)
        except ValueError:
            await interaction.response.send_message("❌ ID phải là số!", ephemeral=True)
            return

        guild = self.bot.get_guild(s_id)
        if not guild:
            await interaction.response.send_message(f"❌ Bot không có mặt trong Server: `{s_id}`", ephemeral=True)
            return

        channel = guild.get_channel(c_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("❌ Không tìm thấy kênh văn bản này!", ephemeral=True)
            return

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO raobai_channels VALUES (?, ?, ?)', (s_id, c_id, guild.name))
        conn.commit()
        conn.close()

        await interaction.response.send_message(f"✅ Đã lưu cấu hình:\n- **Server**: {guild.name}\n- **Kênh**: {channel.name}", ephemeral=True)

    # --- LỆNH RAO BÀI (GIAO DIỆN BẢNG CHỌN) ---
    @app_commands.command(name="raobai", description="Mở menu chọn server để rao bài")
    @app_commands.check(check_quyen)
    async def raobai(self, interaction: discord.Interaction):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT guild_id, guild_name FROM raobai_channels')
        rows = c.fetchall()
        conn.close()

        if not rows:
            await interaction.response.send_message("❌ Chưa có server nào được cấu hình. Dùng `/config_raobai` trước.", ephemeral=True)
            return

        # Tạo danh sách các lựa chọn cho Dropdown menu
        options = [
            discord.SelectOption(
                label="Gửi tất cả Server", 
                value="ALL", 
                description="Rao bài tới mọi server trong danh sách", 
                emoji="🚀"
            )
        ]
        
        # Discord giới hạn menu tối đa 25 lựa chọn, nên ta chỉ lấy 24 server + 1 lựa chọn "ALL"
        for g_id, g_name in rows[:24]:
            options.append(discord.SelectOption(
                label=g_name[:100], # Tên server (giới hạn 100 ký tự)
                value=str(g_id),
                description=f"Rao bài vào server này",
                emoji="💎"
            ))

        # Tạo Embed cho đẹp giống mẫu bạn gửi
        embed = discord.Embed(
            title="🛒 Menu Rao Bài Tự Động",
            description="Chào mừng! Vui lòng chọn một server từ menu bên dưới để gửi bảng giá của Cat Shop.",
            color=discord.Color.purple()
        )

        view = RaobaiView(self.bot, self.db_path, self.img_cat_shop, options)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


    # --- CÁC TÍNH NĂNG KHÁC (GIỮ NGUYÊN) ---
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        is_admin = message.author.id in LIST_ID_ADMINS
        if not is_admin: return
        content = message.content.strip()
        if content in self.auto_responses:
            await message.channel.send(self.auto_responses[content])

    @app_commands.command(name="botmessage", description="Gửi tin nhắn kèm hình ảnh")
    @app_commands.check(check_quyen)
    async def botmessage(self, interaction: discord.Interaction, noidung: str = None, hinhanh: discord.Attachment = None):
        await interaction.response.send_message("ok", ephemeral=True)
        file = await hinhanh.to_file() if hinhanh else None
        await interaction.channel.send(content=noidung, file=file)

    @app_commands.command(name="svv", description="Link svv")
    @app_commands.check(check_quyen)
    async def svv(self, interaction: discord.Interaction):
        await interaction.response.send_message("https://www.roblox.com/share?code=54f7843b34b6334ab95d82efd9952a22&type=Server", ephemeral=True)

    @app_commands.command(name="beequipthatlac", description="Beequip thất lạc")
    async def beequipthatlac(self, interaction: discord.Interaction):
        links = ["https://image2url.com/r2/default/images/1772018251894-78fb3996-7b3f-4fda-9a76-e88ab64fc552.png", 
                 "https://image2url.com/r2/default/images/1772018293232-a4938fdd-cc08-432d-aece-93505cccbee5.png"]
        await interaction.response.send_message("Beequip thất lạc của bố, thằng nào lấy thì cẩn thận")
        for url in links: await interaction.channel.send(url)

    @raobai.error
    @config_raobai.error
    @botmessage.error
    async def quyen_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("Down à mà dùng?", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Chat(bot))