#!/usr/bin/env python3
"""
Cron-fired tee-time booking runner for The Tuesday Man.

Cron line (every Wednesday at 7:25 AM Eastern):
  25 7 * * 3 /opt/tuesdayman/venv/bin/python /opt/tuesdayman/scheduled_runner.py --scheduled >> /opt/tuesdayman/data/cron.log 2>&1

Flags:
  --scheduled  Respect the booking_active toggle; exit quietly if disabled
  --dry-run    Skip wait + Book POST; report slot found or "flow OK"
"""

import argparse
import asyncio
import logging
import sqlite3
import sys
import time as _time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
DATA_DIR    = BASE_DIR / "data"
LOG_FILE    = DATA_DIR / "booking_runner.log"
SCREENSHOTS = DATA_DIR / "screenshots"
DATA_DIR.mkdir(exist_ok=True)
SCREENSHOTS.mkdir(exist_ok=True)

# ── Root logging BEFORE importing book_tee_time ───────────────────────────────
# book_tee_time calls logging.basicConfig() at module level; since root already
# has handlers here, that call is a no-op — all book_tee_time log output flows
# to data/booking_runner.log instead of tee-time-booker/booking.log.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ── Import book_tee_time as an injectable library ─────────────────────────────
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "tee-time-booker"))
import book_tee_time as btt  # noqa: E402  (must come after logging setup)


# ── DB helpers ────────────────────────────────────────────────────────────────

DB_PATH = DATA_DIR / "app.db"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def load_db_config() -> dict:
    """Read config + buddies from SQLite and decrypt the golf password."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM config WHERE id = 1").fetchone()
        if not row:
            raise RuntimeError("No config row found — complete setup first")
        cfg = dict(row)
        buddies = conn.execute(
            "SELECT name, user_id FROM buddies ORDER BY sort_order, id"
        ).fetchall()
        cfg["buddies"] = [{"name": b["name"], "user_id": b["user_id"]} for b in buddies]

    from crypto import decrypt
    cfg["golf_password"] = decrypt(cfg.get("golf_password_enc", ""))
    if not cfg["golf_password"]:
        raise RuntimeError("Failed to decrypt golf_password — check data/.encryption_key")

    # Tell book_tee_time where to write screenshots and raw JSON
    cfg["data_dir"] = str(DATA_DIR)
    return cfg


def write_booking_log(conn, *, status: str, target_date: str = None,
                      target_time: str = None, slot_id: int = None,
                      duration_ms: int = None, log_text: str = None,
                      screenshot_path: str = None, dry_run: bool = False):
    tz = ZoneInfo("America/Toronto")
    ts = datetime.now(tz).isoformat()
    conn.execute(
        """INSERT INTO booking_log
           (timestamp, status, target_date, target_time, slot_id,
            duration_ms, log_text, screenshot_path, dry_run)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (ts, status, target_date, target_time, slot_id,
         duration_ms, log_text, screenshot_path, 1 if dry_run else 0),
    )
    conn.commit()


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_booking(db_cfg: dict, dry_run: bool) -> int:
    """Run the booking flow. Returns 0 on success/dry-run-OK, 1 on failure."""
    btt.load_config(db_cfg)

    target_date = btt.fmt_date(btt.get_next_tuesday())

    log.info("=" * 60)
    log.info(f"scheduled_runner  dry_run={dry_run}  date={target_date}")
    log.info("=" * 60)

    run_args = argparse.Namespace(
        dry_run      = dry_run,
        show_browser = False,
        wait         = not dry_run,  # live run waits until 7:30; dry-run skips
        date         = None,
    )

    t0 = _time.perf_counter()
    try:
        success    = asyncio.run(btt.run(run_args))
        elapsed_ms = int((_time.perf_counter() - t0) * 1000)
    except Exception as exc:
        elapsed_ms = int((_time.perf_counter() - t0) * 1000)
        log.error(f"FATAL in run_booking: {exc}", exc_info=True)
        with get_db() as conn:
            write_booking_log(
                conn,
                status      = "FAIL",
                target_date = target_date,
                duration_ms = elapsed_ms,
                log_text    = str(exc),
                dry_run     = dry_run,
            )
        return 1

    status = "DRY_RUN" if dry_run else ("SUCCESS" if success else "FAIL")
    log.info(f"Result: {status}  ({elapsed_ms} ms)")

    with get_db() as conn:
        write_booking_log(
            conn,
            status      = status,
            target_date = target_date,
            duration_ms = elapsed_ms,
            dry_run     = dry_run,
        )

    return 0 if (success or dry_run) else 1


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Royal Ottawa tee-time booking runner")
    p.add_argument(
        "--scheduled", action="store_true",
        help="Respect booking_active toggle; exit quietly if disabled",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Skip wait and Book POST; report slot found or flow-OK",
    )
    args = p.parse_args()

    try:
        db_cfg = load_db_config()
    except Exception as exc:
        log.error(f"Config load failed: {exc}")
        sys.exit(1)

    if args.scheduled and not db_cfg.get("booking_active", 1):
        log.info("booking_active=0 — skipping this run")
        sys.exit(0)

    rc = run_booking(db_cfg, dry_run=args.dry_run)
    sys.exit(rc)


if __name__ == "__main__":
    main()
