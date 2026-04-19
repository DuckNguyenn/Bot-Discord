from function import db_compat as sqlite3


def init_db():
    sqlite3.ensure_all_tables()


def save_token(user_id, access_token, refresh_token):
    with sqlite3.connect('backup.db') as conn:
        conn.execute('REPLACE INTO oauth_members VALUES (?, ?, ?)', (str(user_id), access_token, refresh_token))
        conn.commit()


def save_simple_id(user_id, guild_id):
    with sqlite3.connect('backup.db') as conn:
        conn.execute('REPLACE INTO member_ids VALUES (?, ?)', (str(user_id), str(guild_id)))
        conn.commit()
