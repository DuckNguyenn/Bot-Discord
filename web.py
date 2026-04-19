import os
from dotenv import load_dotenv
from flask import Flask, request
import requests
import sqlite3

# Tải dữ liệu từ file .env
load_dotenv()

app = Flask(__name__)

# --- CẤU HÌNH TỪ FILE .ENV ---
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'http://localhost:5000/callback')

BOT_TOKEN = os.getenv('BOT_TOKEN')
GUILD_ID = os.getenv('GUILD_ID')
ROLE_ID = os.getenv('ROLE_ID')

DB_NAME = 'backup_users.db'

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users 
                        (user_id TEXT PRIMARY KEY, access_token TEXT, refresh_token TEXT)''')

# --- HÀM XỬ LÝ KÉO MEMBER VÀ CẤP ROLE ---
def add_role_to_member(user_id, access_token):
    if not BOT_TOKEN or not GUILD_ID or not ROLE_ID:
        print("⚠️ Bỏ qua cấp role vì thiếu cấu hình trong file .env")
        return
        
    # BƯỚC 1: Thử kéo user vào server kèm theo Role luôn
    join_url = f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{user_id}"
    join_headers = {
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    join_data = {
        "access_token": access_token,
        "roles": [str(ROLE_ID)]
    }
    
    join_res = requests.put(join_url, headers=join_headers, json=join_data)
    
    # 201: Đã kéo thành công vào server và cấp role
    if join_res.status_code == 201:
        print(f"✅ Đã KÉO user {user_id} vào server và CẤP ROLE!")
        return

    # 204: User ĐÃ CÓ SẴN trong server. Lệnh join sẽ không có tác dụng update role.
    # Nên ta phải chuyển sang BƯỚC 2: Chỉ gọi API cấp Role riêng biệt.
    if join_res.status_code == 204:
        role_url = f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{user_id}/roles/{ROLE_ID}"
        # Thêm json={} để fix lỗi Content-Length của thư viện requests
        role_res = requests.put(role_url, headers={"Authorization": f"Bot {BOT_TOKEN}"}, json={})
        
        if role_res.status_code == 204:
            print(f"✅ Đã CẤP ROLE cho user {user_id} (User đã có sẵn trong server).")
        else:
            print(f"❌ Lỗi Cấp Role: {role_res.status_code} - {role_res.text}")
    else:
        print(f"❌ Lỗi Join Server: {join_res.status_code} - {join_res.text}")

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "❌ Lỗi: Không tìm thấy mã xác nhận (code) từ Discord.", 400

    token_res = requests.post(
        'https://discord.com/api/oauth2/token',
        data={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    ).json()

    if 'access_token' not in token_res:
        return f"❌ Lỗi xác thực từ Discord: {token_res.get('error_description', 'Không rõ lỗi')}", 400

    access_token = token_res['access_token']

    user_res = requests.get(
        'https://discord.com/api/users/@me',
        headers={'Authorization': f"Bearer {access_token}"}
    ).json()
    user_id = user_res['id']

    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('INSERT OR REPLACE INTO users (user_id, access_token, refresh_token) VALUES (?, ?, ?)', 
                     (user_id, access_token, token_res['refresh_token']))

    # TRUYỀN THÊM access_token VÀO HÀM NÀY
    add_role_to_member(user_id, access_token)

    return """
    <div style="font-family: Arial; text-align: center; margin-top: 50px;">
        <h1 style="color: #43b581;">✅ XÁC MINH THÀNH CÔNG!</h1>
        <p style="color: #7289da;"><b>Tài khoản của bạn đã được liên kết hệ thống và nhận Role thành viên.</b></p>
        <p>Bạn có thể đóng tab này và quay lại Discord.</p>
    </div>
    """

if __name__ == '__main__':
    init_db()
    print(f"🚀 Web Server đang chạy tại cổng 5000 (Chờ Discord trả kết quả về {REDIRECT_URI})")
    app.run(port=5000)