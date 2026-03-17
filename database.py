"""
Veritabanı — SQLite
"""
import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "taskbot.db")


def get_conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db():
    with get_conn() as con:
        con.executescript("""
        -- Kullanıcılar
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            timezone    TEXT    DEFAULT 'Europe/Istanbul',
            created_at  TEXT    DEFAULT (datetime('now'))
        );

        -- Kategoriler
        CREATE TABLE IF NOT EXISTS categories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            name        TEXT    NOT NULL,
            emoji       TEXT    DEFAULT '📌',
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );

        -- Görevler
        CREATE TABLE IF NOT EXISTS tasks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            title           TEXT    NOT NULL,
            note            TEXT,
            category_id     INTEGER,
            priority        TEXT    DEFAULT 'orta',   -- yüksek / orta / düşük
            task_type       TEXT    DEFAULT 'daily',  -- daily / weekly / once / recurring
            recur_days      TEXT,                     -- JSON: [0,1,2,3,4] = Pzt-Cum
            scheduled_time  TEXT,                     -- "08:30"
            duration_min    INTEGER DEFAULT 0,
            points          INTEGER DEFAULT 10,
            active          INTEGER DEFAULT 1,
            created_at      TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY(user_id)     REFERENCES users(user_id),
            FOREIGN KEY(category_id) REFERENCES categories(id)
        );

        -- Hatırlatmalar (bir göreve birden fazla)
        CREATE TABLE IF NOT EXISTS reminders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id     INTEGER NOT NULL,
            remind_min  INTEGER NOT NULL,   -- görevden kaç dk önce (0 = tam zamanı)
            FOREIGN KEY(task_id) REFERENCES tasks(id)
        );

        -- Günlük log (yapıldı / yapılmadı)
        CREATE TABLE IF NOT EXISTS daily_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            task_id     INTEGER NOT NULL,
            date        TEXT    NOT NULL,   -- YYYY-MM-DD
            done        INTEGER DEFAULT 0,
            snooze_until TEXT,              -- ISO datetime
            done_at     TEXT,
            UNIQUE(user_id, task_id, date),
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(task_id) REFERENCES tasks(id)
        );

        -- Aktivite takibi (gün içi "şu an ne yapıyorsun")
        CREATE TABLE IF NOT EXISTS activity_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            activity    TEXT    NOT NULL,
            logged_at   TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );

        -- Streak kayıtları
        CREATE TABLE IF NOT EXISTS streaks (
            user_id         INTEGER PRIMARY KEY,
            current_streak  INTEGER DEFAULT 0,
            best_streak     INTEGER DEFAULT 0,
            last_active     TEXT,
            total_points    INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );

        -- Rozetler
        CREATE TABLE IF NOT EXISTS badges (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            badge_key   TEXT    NOT NULL,
            earned_at   TEXT    DEFAULT (datetime('now')),
            UNIQUE(user_id, badge_key),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
        """)
