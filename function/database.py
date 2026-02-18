import sqlite3

def init_db():
    conn = sqlite3.connect('backup.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS oauth_members 
                 (user_id TEXT PRIMARY KEY, access_token TEXT, refresh_token TEXT)''')
    conn.commit()
    conn.close()

def save_token(user_id, access_token, refresh_token):
    conn = sqlite3.connect('backup.db')
    c = conn.cursor()
    c.execute('REPLACE INTO oauth_members VALUES (?, ?, ?)', (user_id, access_token, refresh_token))
    conn.commit()
    conn.close()
    
def save_simple_id(user_id, guild_id):
    conn = sqlite3.connect('backup.db')
    c = conn.cursor()
    # Tạo bảng nếu chưa có
    c.execute('''CREATE TABLE IF NOT EXISTS member_ids 
                 (user_id TEXT PRIMARY KEY, guild_id TEXT)''')
    c.execute('REPLACE INTO member_ids VALUES (?, ?)', (str(user_id), str(guild_id)))
    conn.commit()
    conn.close()