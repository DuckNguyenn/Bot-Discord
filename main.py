import discord
from discord.ext import commands
import asyncio
import threading
import os
from dotenv import load_dotenv
from flask import Flask, request
import requests
from function import database

# --- TẢI CẤU HÌNH TỪ FILE .ENV ---
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID', 0))

# --- KHỞI TẠO WEB SERVER (FLASK) ---
app = Flask(__name__)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "❌ Thiếu mã xác thực!", 400
    
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
    # Tắt log debug của Flask để giảm tốn CPU và rối màn hình console
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
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
        
        # 2. Load các module
        initial_extensions = [
            'function.qr', 'function.chat', 'function.restore', 
            'function.scripts', 'function.vouch', 'buonban.shop', 'function.puff_warn','function.verify'
        ]
        
        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
                print(f"✅ Đã load module: {extension}")
            except Exception as e:
                print(f"❌ Lỗi load module {extension}: {e}")

        await self.tree.sync()
        print("✅ Đã đồng bộ lệnh Slash Command!")

    async def on_ready(self):
        print(f'---')
        print(f'🤖 Bot đã online: {self.user}')
        print(f'🌐 Web Server chạy tại: {REDIRECT_URI}')
        print(f'---')

    async def on_guild_join(self, guild):
        channel = self.get_channel(LOG_CHANNEL_ID)
        if channel:
            embed = discord.Embed(title="📥 Bot vào server mới", color=discord.Color.green())
            embed.add_field(name="Tên", value=guild.name)
            embed.add_field(name="Thành viên", value=guild.member_count)
            await channel.send(embed=embed)

    async def on_app_command_completion(self, interaction, command):
        channel = self.get_channel(LOG_CHANNEL_ID)
        if channel:
            embed = discord.Embed(title="⌨️ Lệnh đã dùng", color=discord.Color.blue())
            embed.add_field(name="User", value=f"{interaction.user}")
            embed.add_field(name="Lệnh", value=f"/{command.name}")
            await channel.send(embed=embed)

async def run_main():
    # Chạy Flask trong thread riêng trước khi chạy Bot
    threading.Thread(target=run_flask, daemon=True).start()
    
    bot = MyBot()
    async with bot:
        await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(run_main())
    except KeyboardInterrupt:
        print("📴 Hệ thống đang tắt...")