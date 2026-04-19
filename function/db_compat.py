import os
import re
import sqlite3 as py_sqlite3
from typing import Any, Dict, Iterable, List, Optional, Sequence

try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*args, **kwargs):
        return False

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', '').strip()

if DATABASE_URL:
    import psycopg
    from psycopg.rows import tuple_row, dict_row
else:
    psycopg = None
    tuple_row = None
    dict_row = None

# Sentinel giống sqlite3.Row
Row = dict

TABLE_PKS: Dict[str, List[str]] = {
    'raobai_channels': ['guild_id'],
    'bot_configs': ['key'],
    'admins': ['user_id'],
    'roles': ['role_id'],
    'learned_responses': ['trigger'],
    'bot_actions': ['action_name'],
    'learning_queue': ['id'],
    'conversation_memory': ['id'],
    'scripts': ['name'],
    'oauth_members': ['user_id'],
    'member_ids': ['user_id'],
    'users': ['user_id'],
    'accounts': ['id'],
}

TABLE_COLS: Dict[str, List[str]] = {
    'raobai_channels': ['guild_id', 'channel_id', 'guild_name'],
    'bot_configs': ['key', 'value'],
    'admins': ['user_id'],
    'roles': ['role_id'],
    'learned_responses': [
        'trigger', 'normalized_trigger', 'response_text', 'response_type', 'match_type',
        'priority', 'enabled', 'created_by', 'usage_count', 'last_used_at', 'created_at'
    ],
    'bot_actions': [
        'action_name', 'trigger', 'normalized_trigger', 'action_type', 'payload', 'match_type',
        'priority', 'enabled', 'created_by', 'usage_count', 'last_used_at', 'created_at'
    ],
    'learning_queue': [
        'id', 'guild_id', 'channel_id', 'user_id', 'username', 'content',
        'normalized_content', 'status', 'note', 'created_at'
    ],
    'conversation_memory': ['id', 'guild_id', 'channel_id', 'user_id', 'role', 'content', 'created_at'],
    'scripts': ['name', 'content'],
    'oauth_members': ['user_id', 'access_token', 'refresh_token'],
    'member_ids': ['user_id', 'guild_id'],
    'users': ['user_id', 'access_token', 'refresh_token'],
    'accounts': ['id', 'guild_id', 'description', 'all_images', 'timestamp'],
}

TEXT_TS_DEFAULT = "to_char(now() at time zone 'UTC', 'YYYY-MM-DD HH24:MI:SS')"

POSTGRES_SCHEMA_SQL = [
    f"""
    create table if not exists raobai_channels (
        guild_id bigint primary key,
        channel_id bigint,
        guild_name text
    )
    """,
    f"""
    create table if not exists bot_configs (
        key text primary key,
        value text
    )
    """,
    "create table if not exists admins (user_id bigint primary key)",
    "create table if not exists roles (role_id bigint primary key)",
    f"""
    create table if not exists learned_responses (
        trigger text primary key,
        normalized_trigger text unique,
        response_text text not null,
        response_type text default 'text',
        match_type text default 'exact',
        priority integer default 100,
        enabled integer default 1,
        created_by bigint,
        usage_count integer default 0,
        last_used_at text,
        created_at text default {TEXT_TS_DEFAULT}
    )
    """,
    f"""
    create table if not exists bot_actions (
        action_name text primary key,
        trigger text not null,
        normalized_trigger text not null,
        action_type text default 'message',
        payload text not null,
        match_type text default 'exact',
        priority integer default 100,
        enabled integer default 1,
        created_by bigint,
        usage_count integer default 0,
        last_used_at text,
        created_at text default {TEXT_TS_DEFAULT}
    )
    """,
    f"""
    create table if not exists learning_queue (
        id bigint generated always as identity primary key,
        guild_id bigint,
        channel_id bigint,
        user_id bigint,
        username text,
        content text,
        normalized_content text,
        status text default 'pending',
        note text,
        created_at text default {TEXT_TS_DEFAULT}
    )
    """,
    f"""
    create table if not exists conversation_memory (
        id bigint generated always as identity primary key,
        guild_id bigint,
        channel_id bigint,
        user_id bigint,
        role text,
        content text,
        created_at text default {TEXT_TS_DEFAULT}
    )
    """,
    "create table if not exists scripts (name text primary key, content text)",
    "create table if not exists oauth_members (user_id text primary key, access_token text, refresh_token text)",
    "create table if not exists member_ids (user_id text primary key, guild_id text)",
    "create table if not exists users (user_id text primary key, access_token text, refresh_token text)",
    f"""
    create table if not exists accounts (
        id bigint generated always as identity primary key,
        guild_id bigint,
        description text,
        all_images text,
        timestamp text default {TEXT_TS_DEFAULT}
    )
    """,
]

SQLITE_SCHEMA_SQL = [
    "create table if not exists raobai_channels (guild_id integer primary key, channel_id integer, guild_name text)",
    "create table if not exists bot_configs (key text primary key, value text)",
    "create table if not exists admins (user_id integer primary key)",
    "create table if not exists roles (role_id integer primary key)",
    '''create table if not exists learned_responses (
        trigger text primary key,
        normalized_trigger text unique,
        response_text text not null,
        response_type text default 'text',
        match_type text default 'exact',
        priority integer default 100,
        enabled integer default 1,
        created_by integer,
        usage_count integer default 0,
        last_used_at text,
        created_at text default current_timestamp
    )''',
    '''create table if not exists bot_actions (
        action_name text primary key,
        trigger text not null,
        normalized_trigger text not null,
        action_type text default 'message',
        payload text not null,
        match_type text default 'exact',
        priority integer default 100,
        enabled integer default 1,
        created_by integer,
        usage_count integer default 0,
        last_used_at text,
        created_at text default current_timestamp
    )''',
    '''create table if not exists learning_queue (
        id integer primary key autoincrement,
        guild_id integer,
        channel_id integer,
        user_id integer,
        username text,
        content text,
        normalized_content text,
        status text default 'pending',
        note text,
        created_at text default current_timestamp
    )''',
    '''create table if not exists conversation_memory (
        id integer primary key autoincrement,
        guild_id integer,
        channel_id integer,
        user_id integer,
        role text,
        content text,
        created_at text default current_timestamp
    )''',
    "create table if not exists scripts (name text primary key, content text)",
    "create table if not exists oauth_members (user_id text primary key, access_token text, refresh_token text)",
    "create table if not exists member_ids (user_id text primary key, guild_id text)",
    "create table if not exists users (user_id text primary key, access_token text, refresh_token text)",
    '''create table if not exists accounts (
        id integer primary key autoincrement,
        guild_id integer,
        description text,
        all_images text,
        timestamp text
    )''',
]

DEFAULT_SEEDS = [
    ("INSERT OR IGNORE INTO bot_configs (key, value) VALUES (?, ?)", ('svv_link', 'https://www.roblox.com/share?code=54f7843b34b6334ab95d82efd9952a22&type=Server')),
    ("INSERT OR IGNORE INTO bot_configs (key, value) VALUES (?, ?)", ('cat_shop_img', 'https://image2url.com/r2/default/images/1772535296937-6abf7344-2758-4427-9926-506918c54c23.png')),
    ("INSERT OR IGNORE INTO bot_configs (key, value) VALUES (?, ?)", ('chatbot_public', '0')),
    ("INSERT OR IGNORE INTO bot_configs (key, value) VALUES (?, ?)", ('chatbot_fuzzy_threshold', '0.86')),
    ("INSERT OR IGNORE INTO bot_configs (key, value) VALUES (?, ?)", ('qr_fallback_img', 'https://image2url.com/r2/default/images/1771410367472-a2a72015-0984-4f08-b4fa-dfab1a117884.png')),
    ("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (1324414978307919895,)),
]



def using_postgres() -> bool:
    return bool(DATABASE_URL and psycopg is not None)


def _normalize_sql(sql: str) -> str:
    return re.sub(r'\s+', ' ', (sql or '').strip())


def _translate_placeholders(sql: str) -> str:
    return sql.replace('?', '%s')


def _split_csv(text: str) -> List[str]:
    return [part.strip() for part in text.split(',') if part.strip()]


def _translate_insert_with_conflict(sql: str, mode: str) -> str:
    normalized = _normalize_sql(sql)
    upper = normalized.upper()
    prefixes = {
        'ignore': 'INSERT OR IGNORE INTO ',
        'replace': 'INSERT OR REPLACE INTO ',
        'replace2': 'REPLACE INTO ',
    }
    if mode == 'ignore' and upper.startswith(prefixes['ignore']):
        body = normalized[len(prefixes['ignore']):]
    elif mode == 'replace' and upper.startswith(prefixes['replace']):
        body = normalized[len(prefixes['replace']):]
    elif mode == 'replace2' and upper.startswith(prefixes['replace2']):
        body = normalized[len(prefixes['replace2']):]
    else:
        return sql

    m = re.match(r'([a-zA-Z_][\w]*)\s*(\(([^)]*)\))?\s*VALUES\s*\((.*)\)$', body, re.IGNORECASE)
    if not m:
        return sql
    table = m.group(1)
    cols_group = m.group(3)
    values_group = m.group(4)
    cols = _split_csv(cols_group) if cols_group else list(TABLE_COLS.get(table, []))
    if not cols:
        return sql
    pk_cols = TABLE_PKS.get(table, [cols[0]])
    quoted_cols = ', '.join(cols)
    translated_values = _translate_placeholders(values_group)
    base = f"INSERT INTO {table} ({quoted_cols}) VALUES ({translated_values})"

    if mode == 'ignore':
        return base + ' ON CONFLICT DO NOTHING'

    update_cols = [col for col in cols if col not in pk_cols]
    if not update_cols:
        return base + f" ON CONFLICT ({', '.join(pk_cols)}) DO NOTHING"
    set_clause = ', '.join(f"{col} = EXCLUDED.{col}" for col in update_cols)
    return base + f" ON CONFLICT ({', '.join(pk_cols)}) DO UPDATE SET {set_clause}"


def _translate_sql(sql: str) -> str:
    normalized = _normalize_sql(sql)
    upper = normalized.upper()

    if upper.startswith('INSERT OR IGNORE INTO '):
        return _translate_insert_with_conflict(normalized, 'ignore')
    if upper.startswith('INSERT OR REPLACE INTO '):
        return _translate_insert_with_conflict(normalized, 'replace')
    if upper.startswith('REPLACE INTO '):
        return _translate_insert_with_conflict(normalized, 'replace2')

    translated = _translate_placeholders(normalized)

    if translated.startswith('INSERT INTO accounts ') and 'RETURNING' not in translated.upper():
        translated += ' RETURNING id'

    return translated


class CursorWrapper:
    def __init__(self, connection: 'ConnectionWrapper'):
        self.connection = connection
        self._lastrowid = None
        rf = dict_row if connection.row_factory is Row else tuple_row
        self._cursor = connection._conn.cursor(row_factory=rf)

    def execute(self, sql: str, params: Optional[Sequence[Any]] = None):
        params = tuple(params or ())
        translated = _translate_sql(sql)
        self._cursor.execute(translated, params)
        self._lastrowid = None
        if translated.upper().startswith('INSERT INTO ACCOUNTS ') and 'RETURNING ID' in translated.upper():
            row = self._cursor.fetchone()
            if row is not None:
                self._lastrowid = row['id'] if isinstance(row, dict) else row[0]
        return self

    def executemany(self, sql: str, params_seq: Iterable[Sequence[Any]]):
        translated = _translate_sql(sql)
        self._cursor.executemany(translated, list(params_seq))
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._lastrowid

    def close(self):
        self._cursor.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


class ConnectionWrapper:
    def __init__(self, dsn: str):
        self._conn = psycopg.connect(dsn)
        self.row_factory = None

    def cursor(self):
        return CursorWrapper(self)

    def execute(self, sql: str, params: Optional[Sequence[Any]] = None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()
        return False


def connect(path: Optional[str] = None):
    if using_postgres():
        return ConnectionWrapper(DATABASE_URL)
    return py_sqlite3.connect(path or 'local.db')


def ensure_all_tables():
    if using_postgres():
        with ConnectionWrapper(DATABASE_URL) as conn:
            cur = conn._conn.cursor()
            for stmt in POSTGRES_SCHEMA_SQL:
                cur.execute(stmt)
        for stmt, params in DEFAULT_SEEDS:
            with connect(None) as conn:
                conn.execute(stmt, params)
    else:
        # SQLite local fallback: tạo cả 3 file local như project gốc
        for path in ('raobai_config.db', 'backup.db', 'backup_users.db', 'shop_acc_v2.db'):
            with py_sqlite3.connect(path) as conn:
                c = conn.cursor()
                for stmt in SQLITE_SCHEMA_SQL:
                    c.execute(stmt)
                conn.commit()
        with connect('raobai_config.db') as conn:
            for stmt, params in DEFAULT_SEEDS:
                conn.execute(stmt, params)
            conn.commit()

