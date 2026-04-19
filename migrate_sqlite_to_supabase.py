import os
import sqlite3
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*args, **kwargs):
        return False

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError("Thiếu DATABASE_URL trong .env")

BATCH_SIZE = int(os.getenv("MIGRATE_BATCH_SIZE", "500"))

import psycopg
from function import db_compat

ROOT = Path(__file__).resolve().parent

SQLITE_SOURCES = {
    "raobai_config.db": ["raobai_channels", "bot_configs", "admins", "roles"],
    "backup.db": ["oauth_members", "member_ids"],
    "backup_users.db": ["users"],
    "shop_acc_v2.db": ["accounts"],
}

IDENTITY_TABLES = {"learning_queue", "conversation_memory", "accounts"}
PRIMARY_KEYS = db_compat.TABLE_PKS
COLUMNS = db_compat.TABLE_COLS


def log(msg: str):
    print(msg, flush=True)


def sqlite_table_exists(db_path: Path, table: str) -> bool:
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table,),
        )
        return cur.fetchone() is not None
    finally:
        con.close()


def rows_from_sqlite(db_path: Path, table: str):
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()

        cols = COLUMNS.get(table)
        if not cols:
            return [], []

        pragma_rows = cur.execute(f"PRAGMA table_info({table})").fetchall()
        existing = [r[1] for r in pragma_rows]
        select_cols = [c for c in cols if c in existing]

        if not select_cols:
            return [], []

        cur.execute(f"SELECT {', '.join(select_cols)} FROM {table}")
        rows = cur.fetchall()
        return select_cols, rows
    finally:
        con.close()


def build_insert(table: str, cols):
    placeholders = ", ".join(["%s"] * len(cols))
    pk_cols = PRIMARY_KEYS[table]
    update_cols = [c for c in cols if c not in pk_cols]

    conflict = f"ON CONFLICT ({', '.join(pk_cols)}) "
    if update_cols:
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        conflict += f"DO UPDATE SET {updates}"
    else:
        conflict += "DO NOTHING"

    overriding = ""
    if table in IDENTITY_TABLES and "id" in cols:
        overriding = " OVERRIDING SYSTEM VALUE"

    return f"INSERT INTO {table} ({', '.join(cols)}){overriding} VALUES ({placeholders}) {conflict}"


def insert_in_batches(cur, conn, sql: str, rows, table_name: str, batch_size: int):
    total = len(rows)
    done = 0

    if total == 0:
        log(f"[OK] {table_name}: 0 rows")
        return

    start_time = time.time()
    log(f"[START] {table_name}: {total} rows | batch_size={batch_size}")

    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        cur.executemany(sql, batch)
        conn.commit()

        done += len(batch)
        elapsed = time.time() - start_time
        rate = done / elapsed if elapsed > 0 else 0

        if done < total:
            log(f"[...] {table_name}: {done}/{total} rows | {rate:.1f} rows/s")
        else:
            log(f"[OK] {table_name}: migrated {done} rows | {rate:.1f} rows/s")


def main():
    log("[INFO] Đang kiểm tra / tạo bảng trên Supabase...")
    db_compat.ensure_all_tables()

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout TO 0")
            cur.execute("SET lock_timeout TO 0")

            for db_name, tables in SQLITE_SOURCES.items():
                db_path = ROOT / db_name

                if not db_path.exists():
                    log(f"[SKIP] {db_name}: không tồn tại")
                    continue

                log(f"[DB] Nguồn: {db_name}")

                for table in tables:
                    try:
                        if table not in COLUMNS or table not in PRIMARY_KEYS:
                            log(f"[SKIP] {table}: chưa có metadata trong db_compat")
                            continue

                        if not sqlite_table_exists(db_path, table):
                            log(f"[SKIP] {table}: không tồn tại trong {db_name}")
                            continue

                        cols, rows = rows_from_sqlite(db_path, table)
                        if not cols:
                            log(f"[SKIP] {table}: không tìm thấy cột phù hợp")
                            continue

                        if not rows:
                            log(f"[OK] {table}: 0 rows")
                            continue

                        sql = build_insert(table, cols)
                        insert_in_batches(cur, conn, sql, rows, table, BATCH_SIZE)

                    except KeyboardInterrupt:
                        log(f"[STOP] Đã dừng khi đang migrate bảng: {table}")
                        raise
                    except Exception as e:
                        conn.rollback()
                        log(f"[ERROR] {table}: {e}")
                        raise

    log("Xong. Dữ liệu đã được đẩy lên Supabase.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Đã dừng bằng tay (Ctrl+C).")
        sys.exit(1)