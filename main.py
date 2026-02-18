import discord
from discord.ext import commands
import asyncio
import threading
from flask import Flask, request
import requests
from function import database

# --- CẤU HÌNH ---
BOT_TOKEN = 'MTQ3MjQ2MjM2MDkwMzAyNDgyMw.G-RJri.xi0nZAjcwTexTT2Xg8P0XrUwqcPxa1OH2cmxBk' 
CLIENT_ID = '1472462360903024823'
CLIENT_SECRET = '65r2lmfTnI8AeMn1K4mqXWr1rZ0FNoX0'
REDIRECT_URI = 'http://localhost:5000/callback'

# --- KHỞI TẠO WEB SERVER (FLASK) ---
app = Flask(__name__)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "❌ Thiếu mã xác thực (Code)!", 400
    
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    r = requests.post('https://discord.com/api/v10/oauth2/token', data=data, headers=headers)
    token_data = r.json()

    if 'access_token' in token_data:
        user_headers = {'Authorization': f"Bearer {token_data['access_token']}"}
        user_info = requests.get('https://discord.com/api/v10/users/@me', headers=user_headers).json()
        
        database.save_token(user_info['id'], token_data['access_token'], token_data['refresh_token'])
        return f"✅ Backup thành công cho {user_info['username']}!"
    
    return "❌ Lỗi xác thực OAuth2.", 400

def run_flask():
    app.run(port=5000, debug=False, use_reloader=False)

# --- CẤU HÌNH DISCORD BOT ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True 
        intents.members = True 
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # 1. Khởi tạo database
        database.init_db()
        
        # 2. FIX ĐƯỜNG DẪN MODULE Ở ĐÂY
        # Khi file nằm trong thư mục 'function', ta phải gọi là 'function.ten_file'
        initial_extensions = ['function.qr', 'function.chat', 'function.restore', 'function.scripts', 'function.vouch', 'buonban.shop']
        
        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
                print(f"✅ Đã load module: {extension}")
            except Exception as e:
                # In ra lỗi chi tiết để debug
                print(f"❌ Không thể load module {extension}: {e}")

        await self.tree.sync()
        print("✅ Đã đồng bộ lệnh Slash Command!")

    async def on_ready(self):
        print(f'---')
        print(f'🤖 Bot đã online: {self.user}')
        print(f'🌐 Web Server chạy tại: {REDIRECT_URI}')
        print(f'---')
        
  #  async def on_message(self, message):
   #     if message.author == self.user:
    #        return
     #   if self.user.mentioned_in(message):
      #      await message.reply("ping cc")
       # await self.process_commands(message)

async def run_bot():
    threading.Thread(target=run_flask, daemon=True).start()
    
    bot = MyBot()
    async with bot:
        await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("📴 Hệ thống đang tắt...")

# Thêm vào class MyBot trong main.py
async def on_guild_join(self, guild):
    # Thay ID_KENH_LOG bằng ID kênh Discord của bạn để nhận thông báo
    log_channel_id = 1381782571460985013 
    channel = self.get_channel(log_channel_id)
    
    if channel:
        embed = discord.Embed(title="📥 Bot đã được thêm vào server mới!", color=discord.Color.green())
        embed.add_field(name="Tên Server", value=guild.name, inline=True)
        embed.add_field(name="ID Server", value=guild.id, inline=True)
        embed.add_field(name="Số lượng thành viên", value=guild.member_count, inline=False)
        if guild.owner:
            embed.add_field(name="Chủ Server", value=f"{guild.owner} ({guild.owner.id})", inline=False)
        
        await channel.send(embed=embed)
        
# Thêm vào class MyBot trong main.py
async def setup_hook(self):
    # ... (giữ nguyên các code cũ của bạn) ...
    self.tree.on_error = self.on_app_command_error # Để theo dõi cả lỗi nếu muốn

@commands.Cog.listener()
async def on_app_command_completion(self, interaction: discord.Interaction, command: discord.app_commands.Command):
    log_channel_id = 1381782571460985013 
    channel = self.get_channel(log_channel_id)
    
    if channel:
        embed = discord.Embed(title="⌨️ Lệnh đã được sử dụng", color=discord.Color.blue())
        embed.add_field(name="Người dùng", value=f"{interaction.user} ({interaction.user.id})", inline=True)
        embed.add_field(name="Lệnh", value=f"/{command.name}", inline=True)
        embed.add_field(name="Server", value=f"{interaction.guild.name if interaction.guild else 'DM'}", inline=False)
        
        await channel.send(embed=embed)