import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import asyncio

DB_PATH = 'raobai_config.db'
ROOT_ADMIN = 1126531490793148427 # Không bao giờ bị mất quyền

# --- HỆ THỐNG KIỂM TRA QUYỀN TRONG DATABASE ---
def check_quyen(interaction: discord.Interaction) -> bool:
    if interaction.user.id == ROOT_ADMIN:
        return True
        
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        # 1. Kiểm tra xem có phải Admin không
        c.execute('SELECT user_id FROM admins WHERE user_id = ?', (interaction.user.id,))
        if c.fetchone():
            return True
            
        # 2. Kiểm tra xem có Role được phép không
        user_role_ids = [role.id for role in interaction.user.roles]
        if not user_role_ids:
            return False
            
        placeholders = ','.join('?' * len(user_role_ids))
        c.execute(f'SELECT role_id FROM roles WHERE role_id IN ({placeholders})', user_role_ids)
        if c.fetchone():
            return True
            
    return False

# --- CLASS GIAO DIỆN MENU CHỌN SERVER (/RAOBAI) ---
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
        await interaction.response.defer(ephemeral=True)
        selected_value = self.values[0]
        
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            if selected_value == "ALL":
                c.execute('SELECT * FROM raobai_channels')
            else:
                s_id = int(selected_value)
                c.execute('SELECT * FROM raobai_channels WHERE guild_id = ?', (s_id,))
            rows = c.fetchall()

        success = 0
        report = []
        
        for g_id, c_id, g_name in rows:
            channel = self.bot.get_channel(c_id)
            if channel:
                try:
                    await channel.send(self.img_cat_shop)
                    success += 1
                    report.append(f"✅ Đã gửi tới `{g_name}`")
                    await asyncio.sleep(1)
                except discord.Forbidden:
                    report.append(f"❌ `{g_name}`: Lỗi quyền gửi bài")
                except Exception as e:
                     report.append(f"❌ `{g_name}`: Lỗi {e}")
            else:
                report.append(f"❓ `{g_name}`: Không tìm thấy kênh")

        result_msg = "**Báo cáo Rao Bài:**\n" + "\n".join(report)
        await interaction.followup.send(f"{result_msg}\n\n**Tổng cộng thành công: {success}/{len(rows)}**", ephemeral=True)

class RaobaiView(discord.ui.View):
    def __init__(self, bot, db_path, img_cat_shop, options):
        super().__init__(timeout=120)
        self.add_item(RaobaiSelect(bot, db_path, img_cat_shop, options))

# --- MAIN COG: CHAT ---
class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = DB_PATH
        self.init_db()
        
        self.auto_responses = {
            "MH": "https://image2url.com/r2/default/images/1772188399025-059f4532-b46c-4341-a2f3-44cac9212ec6.png",
            "qr": "https://image2url.com/r2/default/images/1771410367472-a2a72015-0984-4f08-b4fa-dfab1a117884.png",
            "toi xin hua": "Trong trường hợp nhóm này bị điều tra bởi các cơ quan trực thuộc bộ công an (hoặc các tổ chức chính trị tương tự phục vụ cho nhà nước CHXHCNVN), tôi khẳng định mình không liên quan tới nhóm hoặc những cá nhân khác trong nhóm này. Tôi không rõ tại sao mình lại có mặt ở đây vào thời điểm này, có lẽ tài khoản của tôi đã được thêm bởi một bên thứ ba. Tôi cũng xin khẳng định rằng mình không hề giúp sức cho những hành động chống phá Đảng và nhà nước của các thành viên trong nhóm này.",
            "hoang luan 40k": "https://image2url.com/r2/default/images/1772295505216-f8e6d11a-b1fd-4cb8-abb1-b018a933664a.png",
            "tao ticket":"Tạo ticket cày thuê ở #ticket🎫 , sau đó chọn mục đích tạo ticket nha. https://image2url.com/r2/default/videos/1773334019456-f2a13ca7-346c-4742-adf2-88e11eb61957.mp4",
            "tạo ticket":"Tạo ticket cày thuê ở #ticket🎫 , sau đó chọn mục đích tạo ticket nha. https://image2url.com/r2/default/videos/1773334019456-f2a13ca7-346c-4742-adf2-88e11eb61957.mp4"
        }

    # --- HỆ THỐNG DATABASE ---
    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS raobai_channels (guild_id INTEGER PRIMARY KEY, channel_id INTEGER, guild_name TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS bot_configs (key TEXT PRIMARY KEY, value TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)''')
            c.execute('''CREATE TABLE IF NOT EXISTS roles (role_id INTEGER PRIMARY KEY)''')
            
            c.execute("INSERT OR IGNORE INTO bot_configs VALUES ('svv_link', 'https://www.roblox.com/share?code=54f7843b34b6334ab95d82efd9952a22&type=Server')")
            c.execute("INSERT OR IGNORE INTO bot_configs VALUES ('cat_shop_img', 'https://image2url.com/r2/default/images/1772535296937-6abf7344-2758-4427-9926-506918c54c23.png')")
            # Ghi sẵn một số ID Admin cũ của bạn
            c.execute("INSERT OR IGNORE INTO admins VALUES (1324414978307919895)")

    def get_config(self, key: str) -> str:
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM bot_configs WHERE key = ?", (key,))
            row = c.fetchone()
            return row[0] if row else None

    def set_config(self, key: str, value: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO bot_configs (key, value) VALUES (?, ?)", (key, value))

    # ==========================================
    # --- QUẢN LÝ QUYỀN HẠN TRỰC TIẾP TỪ BOT ---
    # ==========================================
    quyen_group = app_commands.Group(name="quyen", description="Quản lý quyền sử dụng bot")

    @quyen_group.command(name="add_admin", description="Thêm một người vào danh sách Admin bot")
    @app_commands.check(check_quyen)
    async def add_admin(self, interaction: discord.Interaction, member: discord.Member):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR IGNORE INTO admins VALUES (?)", (member.id,))
        await interaction.response.send_message(f"✅ Đã cấp quyền Admin bot cho {member.mention}", ephemeral=True)

    @quyen_group.command(name="remove_admin", description="Xóa một người khỏi danh sách Admin bot")
    @app_commands.check(check_quyen)
    async def remove_admin(self, interaction: discord.Interaction, member: discord.Member):
        if member.id == ROOT_ADMIN:
            await interaction.response.send_message("❌ Không thể xóa Root Admin!", ephemeral=True)
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM admins WHERE user_id = ?", (member.id,))
        await interaction.response.send_message(f"🗑️ Đã thu hồi quyền Admin bot của {member.mention}", ephemeral=True)

    @quyen_group.command(name="add_role", description="Cho phép một Role được dùng bot")
    @app_commands.check(check_quyen)
    async def add_role(self, interaction: discord.Interaction, role: discord.Role):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR IGNORE INTO roles VALUES (?)", (role.id,))
        await interaction.response.send_message(f"✅ Những ai có role {role.mention} giờ đã có thể dùng bot.", ephemeral=True)

    @quyen_group.command(name="remove_role", description="Xóa Role khỏi danh sách được phép")
    @app_commands.check(check_quyen)
    async def remove_role(self, interaction: discord.Interaction, role: discord.Role):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM roles WHERE role_id = ?", (role.id,))
        await interaction.response.send_message(f"🗑️ Đã tước quyền sử dụng bot của role {role.name}", ephemeral=True)

    # --- CÁC LỆNH CŨ ---
    @app_commands.command(name="set_svv", description="Thay đổi link Server VIP")
    @app_commands.describe(link_moi="Dán link SVV mới vào đây")
    @app_commands.check(check_quyen)
    async def set_svv(self, interaction: discord.Interaction, link_moi: str):
        self.set_config('svv_link', link_moi)
        await interaction.response.send_message(f"✅ Đã cập nhật link SVV mới:\n{link_moi}", ephemeral=True)

    @app_commands.command(name="set_catshop", description="Thay đổi ảnh bảng giá Cat Shop")
    @app_commands.describe(link_anh="Dán link ảnh mới (dùng image2url) vào đây")
    @app_commands.check(check_quyen)
    async def set_catshop(self, interaction: discord.Interaction, link_anh: str):
        self.set_config('cat_shop_img', link_anh)
        await interaction.response.send_message(f"✅ Đã cập nhật ảnh bảng giá Cat Shop mới thành công!", ephemeral=True)

    @app_commands.command(name="svv", description="Lấy link Server VIP hiện tại")
    @app_commands.check(check_quyen)
    async def svv(self, interaction: discord.Interaction):
        link_hien_tai = self.get_config('svv_link')
        await interaction.response.send_message(link_hien_tai, ephemeral=True)

    @app_commands.command(name="banggia", description="Bảng giá Cat's shop")
    async def banggia(self, interaction: discord.Interaction):
        anh_hien_tai = self.get_config('cat_shop_img')
        await interaction.response.send_message(anh_hien_tai)

    @app_commands.command(name="raobai", description="Mở menu chọn server để rao bài")
    @app_commands.check(check_quyen)
    async def raobai(self, interaction: discord.Interaction):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('SELECT guild_id, guild_name FROM raobai_channels')
            rows = c.fetchall()

        if not rows:
            await interaction.response.send_message("❌ Chưa có server nào được cấu hình.", ephemeral=True)
            return

        options = [discord.SelectOption(label="Gửi tất cả Server", value="ALL", emoji="🚀")]
        for g_id, g_name in rows[:24]:
            options.append(discord.SelectOption(label=g_name[:100], value=str(g_id), emoji="💎"))

        embed = discord.Embed(
            title="🛒 Menu Rao Bài Tự Động",
            description="Chào mừng! Vui lòng chọn một server từ menu bên dưới.",
            color=discord.Color.purple()
        )

        current_cat_shop_img = self.get_config('cat_shop_img')
        view = RaobaiView(self.bot, self.db_path, current_cat_shop_img, options)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="config_raobai", description="Cấu hình rao bài bằng ID Server và ID Kênh")
    @app_commands.describe(server_id="Nhập ID Server", channel_id="Nhập ID Kênh")
    @app_commands.check(check_quyen)
    async def config_raobai(self, interaction: discord.Interaction, server_id: str, channel_id: str):
        try:
            s_id, c_id = int(server_id), int(channel_id)
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

        with sqlite3.connect(self.db_path) as conn:
            conn.execute('INSERT OR REPLACE INTO raobai_channels VALUES (?, ?, ?)', (s_id, c_id, guild.name))

        await interaction.response.send_message(f"✅ Đã lưu: **{guild.name}** - **{channel.name}**", ephemeral=True)

    @app_commands.command(name="botmessage", description="Gửi tin nhắn qua bot")
    @app_commands.check(check_quyen)
    async def botmessage(self, interaction: discord.Interaction, noidung: str = None, hinhanh: discord.Attachment = None):
        await interaction.response.send_message("ok", ephemeral=True)
        file = await hinhanh.to_file() if hinhanh else None
        await interaction.channel.send(content=noidung, file=file)

    @app_commands.command(name="beequipthatlac", description="Beequip thất lạc")
    async def beequipthatlac(self, interaction: discord.Interaction):
        links = ["https://image2url.com/r2/default/images/1772018251894-78fb3996-7b3f-4fda-9a76-e88ab64fc552.png", 
                 "https://image2url.com/r2/default/images/1772018293232-a4938fdd-cc08-432d-aece-93505cccbee5.png"]
        await interaction.response.send_message("Beequip thất lạc của bố, thằng nào lấy thì cẩn thận")
        for url in links: await interaction.channel.send(url)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        
        # Chỉ quét nội dung nếu người dùng có quyền
        # Lưu ý: Lệnh on_message hơi đặc biệt nên ta gọi hàm check_quyen thủ công
        class FakeInteraction:
            user = message.author
        if not check_quyen(FakeInteraction()): return
        
        content = message.content.strip()
        if content == "cat shop":
            anh_hien_tai = self.get_config('cat_shop_img')
            await message.channel.send(anh_hien_tai)
        elif content in self.auto_responses:
            await message.channel.send(self.auto_responses[content])

    @raobai.error
    @config_raobai.error
    @botmessage.error
    @svv.error
    @set_svv.error
    @set_catshop.error
    async def quyen_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(f"Down à mà dùng?\n*(ID: `{interaction.user.id}`)*", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Chat(bot))