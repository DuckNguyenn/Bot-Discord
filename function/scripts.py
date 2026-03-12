import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import io

# --- ĐỒNG BỘ DATABASE VÀ QUYỀN HẠN ---
# Trỏ file database về chung 1 chỗ với chat.py
DB_PATH = 'raobai_config.db'
ROOT_ADMIN = 1126531490793148427

def check_quyen(interaction: discord.Interaction) -> bool:
    if interaction.user.id == ROOT_ADMIN:
        return True
        
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        # 1. Kiểm tra Admin trong DB
        c.execute('SELECT user_id FROM admins WHERE user_id = ?', (interaction.user.id,))
        if c.fetchone():
            return True
            
        # 2. Kiểm tra Role trong DB
        user_role_ids = [role.id for role in interaction.user.roles]
        if not user_role_ids:
            return False
            
        placeholders = ','.join('?' * len(user_role_ids))
        c.execute(f'SELECT role_id FROM roles WHERE role_id IN ({placeholders})', user_role_ids)
        if c.fetchone():
            return True
            
    return False

class Scripts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = DB_PATH
        self.init_db()

    # --- KHỞI TẠO BẢNG SCRIPTS ---
    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # Chỉ tạo thêm bảng scripts (các bảng admins/roles đã được chat.py lo)
            conn.execute('''CREATE TABLE IF NOT EXISTS scripts 
                            (name TEXT PRIMARY KEY, content TEXT)''')
            
            # Tự động nạp 2 script cũ vào database trong lần chạy đầu tiên
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM scripts")
            if c.fetchone()[0] == 0:
                atlas_code = 'loadstring(game:HttpGet("https://raw.githubusercontent.com/Chris12089/atlasbss/main/script.lua"))()'
                vichop_code = """_G.hook = "" -- discord webhook url (optional)
_G.uid = "" -- discord user id for ping (optional)
_G.delay = "0" -- delay before server hop in seconds
_G.minlvl = "1" -- minimum vic level to attack (1-12)
_G.maxlvl = "12" -- maximum vic level to attack (1-12)
_G.onlygifted = false -- true = only attack/find gifted vics, false = any
_G.room = "" -- sync room name for searcher system (optional, any name)
_G.mainuser = "" -- main user for auto searcher system (optional)
_G.mainwait = true -- true = main waits for searchers, false = main hops if no vics in list

loadstring(game:HttpGet("https://raw.githubusercontent.com/1toop/vichop/main/hop.lua"))()"""
                conn.execute("INSERT INTO scripts (name, content) VALUES (?, ?)", ("atlas", atlas_code))
                conn.execute("INSERT INTO scripts (name, content) VALUES (?, ?)", ("vichop", vichop_code))

    # --- LỆNH XEM SCRIPT (Dành cho mọi người) ---
    @app_commands.command(name="script", description="Lấy mã script theo tên")
    @app_commands.describe(ten="Tên script muốn lấy")
    async def get_script(self, interaction: discord.Interaction, ten: str):
        ten_clean = ten.lower()
        
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT content FROM scripts WHERE name = ?", (ten_clean,))
            row = c.fetchone()

        if row:
            script_content = row[0]
            embed = discord.Embed(color=discord.Color.gold())
            
            if len(script_content) > 4000:
                embed.description = f"**{ten_clean}**\n*(Code quá dài nên bot đã đính kèm thành file .lua ở dưới)*"
                file_to_send = discord.File(io.BytesIO(script_content.encode('utf-8')), filename=f"{ten_clean}.lua")
                await interaction.response.send_message(embed=embed, file=file_to_send)
            else:
                embed.description = f"**{ten_clean}**\n```lua\n{script_content}\n```"            
                await interaction.response.send_message(embed=embed)
        else:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("SELECT name FROM scripts")
                all_names = [r[0] for r in c.fetchall()]
            
            danh_sach = ", ".join(all_names) if all_names else "Chưa có script nào"
            await interaction.response.send_message(
                f"❌ Không tìm thấy script tên `{ten}`.\nCác script hiện có: `{danh_sach}`", 
                ephemeral=True
            )

    # --- LỆNH THÊM / CẬP NHẬT SCRIPT (Dành cho Admin) ---
    @app_commands.command(name="set_script", description="Thêm mới hoặc cập nhật nội dung script")
    @app_commands.describe(
        ten="Tên gọi của script", 
        noidung="Dán code vào đây (đối với code ngắn)",
        file_code="Hoặc tải file .lua / .txt lên đây (đối với code siêu dài)"
    )
    @app_commands.check(check_quyen)
    async def set_script(self, interaction: discord.Interaction, ten: str, noidung: str = None, file_code: discord.Attachment = None):
        await interaction.response.defer(ephemeral=True)
        
        script_content = ""
        
        if file_code:
            try:
                script_bytes = await file_code.read()
                script_content = script_bytes.decode('utf-8')
            except Exception as e:
                await interaction.followup.send(f"❌ Lỗi khi đọc file đính kèm: {e}")
                return
        elif noidung:
            script_content = noidung
        else:
            await interaction.followup.send("❌ Bạn phải nhập `noidung` hoặc đính kèm `file_code`!", ephemeral=True)
            return

        ten_clean = ten.lower()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO scripts (name, content) VALUES (?, ?)", (ten_clean, script_content))
            
        await interaction.followup.send(f"✅ Đã lưu script `{ten_clean}` thành công!", ephemeral=True)

    # --- LỆNH XÓA SCRIPT (Dành cho Admin) ---
    @app_commands.command(name="del_script", description="Xóa một script khỏi hệ thống")
    @app_commands.describe(ten="Tên script muốn xóa")
    @app_commands.check(check_quyen)
    async def del_script(self, interaction: discord.Interaction, ten: str):
        ten_clean = ten.lower()
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM scripts WHERE name = ?", (ten_clean,))
            if c.rowcount > 0:
                await interaction.response.send_message(f"🗑️ Đã xóa script `{ten_clean}`.", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ Không tìm thấy script tên `{ten_clean}` để xóa.", ephemeral=True)

    @set_script.error
    @del_script.error
    async def quyen_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message("❌ Bạn không có quyền quản lý script!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Scripts(bot))