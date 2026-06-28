import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parent.parent / "server" / "data" / "arxiv_qa.db"

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ai_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(user_id),
            question   TEXT NOT NULL,
            answer_count INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            hidden     INTEGER NOT NULL DEFAULT 0,
            pinned     INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS ai_answers (
            answer_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   INTEGER NOT NULL REFERENCES ai_sessions(session_id),
            slot         INTEGER NOT NULL,
            thinking     TEXT,
            answer       TEXT,
            generated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS benchmark_sessions (
            session_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL REFERENCES users(user_id),
            title          TEXT DEFAULT '',
            problem        TEXT DEFAULT '',
            origin         TEXT DEFAULT '',
            solution       TEXT DEFAULT '',
            rubric         TEXT DEFAULT '',
            doubao_answer  TEXT DEFAULT '',
            doubao_analysis TEXT DEFAULT '',
            created_at     TEXT NOT NULL,
            updated_at     TEXT NOT NULL,
            hidden         INTEGER NOT NULL DEFAULT 0,
            pinned         INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS benchmark_outputs (
            output_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   INTEGER NOT NULL UNIQUE REFERENCES benchmark_sessions(session_id),
            tex_content  TEXT,
            status       TEXT DEFAULT 'pending',
            generated_at TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_answers_session_slot ON ai_answers(session_id, slot);
    """)
    for col in [("hidden", 0), ("pinned", 0)]:
        try:
            conn.execute(f"ALTER TABLE ai_sessions ADD COLUMN {col[0]} INTEGER NOT NULL DEFAULT {col[1]}")
        except sqlite3.OperationalError:
            pass
    # Fix: old schema had 'count' instead of 'answer_count'
    try:
        conn.execute("ALTER TABLE ai_sessions ADD COLUMN answer_count INTEGER NOT NULL DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    # Migrate: add title/pinned to benchmark_sessions if upgrading
    for col, default in [("title", "''"), ("pinned", "0")]:
        try:
            conn.execute(f"ALTER TABLE benchmark_sessions ADD COLUMN {col} TEXT DEFAULT {default}" if col == "title"
                         else f"ALTER TABLE benchmark_sessions ADD COLUMN {col} INTEGER NOT NULL DEFAULT {default}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()
