import aiosqlite
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "database.sqlite")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cached_media (
                shortcode TEXT PRIMARY KEY,
                media_type TEXT,
                file_ids TEXT,
                caption TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS downloads_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                shortcode TEXT,
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def add_or_update_user(user_id: int, username: str, first_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name
        """, (user_id, username, first_name))
        await db.commit()

async def get_cached(shortcode: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT media_type, file_ids, caption FROM cached_media WHERE shortcode = ?
        """, (shortcode,))
        row = await cursor.fetchone()
        if row:
            media_type, file_ids_json, caption = row
            return {
                "media_type": media_type,
                "file_ids": json.loads(file_ids_json),
                "caption": caption
            }
        return None

async def save_cache(shortcode: str, media_type: str, file_ids: list, caption: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO cached_media (shortcode, media_type, file_ids, caption)
            VALUES (?, ?, ?, ?)
        """, (shortcode, media_type, json.dumps(file_ids), caption))
        await db.commit()

async def log_download(user_id: int, shortcode: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO downloads_log (user_id, shortcode) VALUES (?, ?)
        """, (user_id, shortcode))
        await db.commit()

async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor_users = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor_users.fetchone())[0]

        cursor_downloads = await db.execute("SELECT COUNT(*) FROM downloads_log")
        total_downloads = (await cursor_downloads.fetchone())[0]

        cursor_cached = await db.execute("SELECT COUNT(*) FROM cached_media")
        total_cached = (await cursor_cached.fetchone())[0]

        return {
            "users": total_users,
            "downloads": total_downloads,
            "cached": total_cached
        }
