import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    app_password_hash   TEXT,
    golf_username       TEXT,
    golf_password_enc   TEXT,
    preferred_times     TEXT    DEFAULT '["7:30 AM","7:20 AM","7:40 AM"]',
    play_day            INTEGER DEFAULT 1,
    booking_opens_hour  INTEGER DEFAULT 7,
    booking_opens_min   INTEGER DEFAULT 30,
    timezone            TEXT    DEFAULT 'America/Toronto',
    booking_active      INTEGER DEFAULT 1,
    course_event_id     TEXT    DEFAULT '2079',
    course_url_id       TEXT    DEFAULT '27',
    course_json_id      INTEGER DEFAULT 1,
    buddy_group_id      TEXT    DEFAULT '73',
    martin_user_id      INTEGER DEFAULT 755,
    notification_email  TEXT,
    notify_success      INTEGER DEFAULT 1,
    notify_fallback     INTEGER DEFAULT 1,
    notify_failure      INTEGER DEFAULT 1,
    notify_drift        INTEGER DEFAULT 1,
    notify_weekly       INTEGER DEFAULT 0,
    inspector_hour      INTEGER DEFAULT 23,
    inspector_min       INTEGER DEFAULT 0,
    setup_complete      INTEGER DEFAULT 0,
    profile_picture     TEXT
);

CREATE TABLE IF NOT EXISTS buddies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    user_id     INTEGER,
    color       TEXT    DEFAULT '#2C5840',
    sort_order  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS booking_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    status          TEXT    NOT NULL,
    target_date     TEXT,
    target_time     TEXT,
    slot_id         INTEGER,
    duration_ms     INTEGER,
    log_text        TEXT,
    screenshot_path TEXT,
    dry_run         INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS inspector_runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT    NOT NULL,
    overall_status    TEXT    NOT NULL,
    report_json       TEXT    NOT NULL,
    changes_detected  INTEGER DEFAULT 0,
    notification_sent INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS inspector_snapshots (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT NOT NULL,
    page_name    TEXT NOT NULL,
    html_hash    TEXT NOT NULL,
    html_snippet TEXT,
    selectors_json TEXT
);
"""

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
        conn.execute("INSERT OR IGNORE INTO config (id) VALUES (1)")
        # Migrations for columns added after initial release
        for col, definition in [
            ('profile_picture', 'TEXT'),
        ]:
            try:
                conn.execute(f"ALTER TABLE config ADD COLUMN {col} {definition}")
            except Exception:
                pass
        # Fix course_json_id: undo incorrect migration that set it to 2 (Royal Nine).
        # Main Course = 1, Royal Nine = 2.
        conn.execute(
            "UPDATE config SET course_json_id = 1 WHERE id = 1 AND course_json_id = 2"
        )
        conn.commit()
