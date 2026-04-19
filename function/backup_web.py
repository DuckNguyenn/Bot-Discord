from flask import Flask, request
import requests
from function import database

app = Flask(__name__)

CLIENT_ID = 'ID_BOT_CUA_BAN'
CLIENT_SECRET = 'SECRET_BOT_CUA_BAN'
REDIRECT_URI = 'http://localhost:5000/callback'

@app.route('/callback')
def callback():
    code = request.args.get('code')
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

    # Lấy ID user
    user_headers = {'Authorization': f"Bearer {token_data['access_token']}"}
    user_info = requests.get('https://discord.com/api/v10/users/@me', headers=user_headers).json()

    database.save_token(user_info['id'], token_data['access_token'], token_data['refresh_token'])
    return "✅ Đã Backup thành công!"

if __name__ == '__main__':
    database.init_db()
    app.run(port=5000)