#!/usr/bin/env python3
"""
Royal Ottawa Golf Club — Automated Tee Time Booker
====================================================
Run on Wednesday morning to book the best Tuesday-morning slot
the moment bookings open at 7:30 AM Eastern.

Usage:
  py book_tee_time.py --wait            # log in now, wait, fire at 7:30:00.000
  py book_tee_time.py --dry-run         # everything except the final POST
  py book_tee_time.py --show-browser    # visible browser for debugging
  py book_tee_time.py --date "Tue, Jun 09 2026"  # override target date

Typical Wednesday workflow:
  py book_tee_time.py --wait            # run at any time before 7:30 AM

Call load_config('file') or load_config(db_dict) before run() or any step function.
"""

import asyncio
import argparse
import json
import logging
import sys
import time as _time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.async_api import (
    async_playwright, Browser, BrowserContext, Page, Response
)

# ── Module globals (populated by load_config before any function is called) ───
USERNAME              = ""
PASSWORD              = ""
PREFERRED_TIMES: list = ["7:30 AM", "7:20 AM", "7:40 AM"]
COURSE_EVENT_ID       = "2079"
COURSE_URL_ID         = "27"
COURSE_JSON_ID        = 1
BUDDIES: list         = []
BUDDY_GROUP_ID        = "73"
BUDDY_USER_IDS: dict  = {}
TIMEZONE              = "America/Toronto"
BOOKING_OPENS_HOUR    = 7
BOOKING_OPENS_MINUTE  = 30
BASE_URL              = "https://royalottawagolfclub.teetimes.totalclubunity.com"
PLAY_DAY              = 1   # 0=Mon, 1=Tue, ..., 6=Sun


def load_config(source) -> None:
    """
    Populate module globals.
      load_config('file')  - read from config.py (standalone / dev use)
      load_config(dict)    - inject from a DB config dict (scheduled_runner)
    Must be called before run() or any step function.
    """
    global USERNAME, PASSWORD, PREFERRED_TIMES, COURSE_EVENT_ID, COURSE_URL_ID
    global COURSE_JSON_ID, BUDDIES, BUDDY_GROUP_ID, BUDDY_USER_IDS
    global TIMEZONE, BOOKING_OPENS_HOUR, BOOKING_OPENS_MINUTE, BASE_URL
    global SCREENSHOTS, RAW_JSON_FILE, TZ, PLAY_DAY

    if source == "file":
        from config import (
            USERNAME as _U, PASSWORD as _P,
            PREFERRED_TIMES as _PT, COURSE_EVENT_ID as _CEI, COURSE_URL_ID as _CUI,
            COURSE_JSON_ID as _CJI, BUDDIES as _B, BUDDY_GROUP_ID as _BGI,
            BUDDY_USER_IDS as _BUID, TIMEZONE as _TZ,
            BOOKING_OPENS_HOUR as _BOH, BOOKING_OPENS_MINUTE as _BOM,
            BASE_URL as _BU,
        )
        USERNAME              = _U
        PASSWORD              = _P
        PREFERRED_TIMES       = _PT
        COURSE_EVENT_ID       = _CEI
        COURSE_URL_ID         = _CUI
        COURSE_JSON_ID        = _CJI
        BUDDIES               = _B
        BUDDY_GROUP_ID        = _BGI
        BUDDY_USER_IDS        = _BUID
        TIMEZONE              = _TZ
        BOOKING_OPENS_HOUR    = _BOH
        BOOKING_OPENS_MINUTE  = _BOM
        BASE_URL              = _BU
        # Paths stay relative to tee-time-booker/ for standalone use
    else:
        cfg                   = source
        USERNAME              = cfg["golf_username"]
        PASSWORD              = cfg["golf_password"]   # already decrypted
        PREFERRED_TIMES       = json.loads(cfg.get("preferred_times", '["7:30 AM","7:20 AM","7:40 AM"]'))
        COURSE_EVENT_ID       = str(cfg.get("course_event_id", "2079"))
        COURSE_URL_ID         = str(cfg.get("course_url_id", "27"))
        COURSE_JSON_ID        = int(cfg.get("course_json_id", 1))
        BUDDY_GROUP_ID        = str(cfg.get("buddy_group_id", "73"))
        TIMEZONE              = cfg.get("timezone", "America/Toronto")
        BOOKING_OPENS_HOUR    = int(cfg.get("booking_opens_hour", 7))
        BOOKING_OPENS_MINUTE  = int(cfg.get("booking_opens_min", 30))
        BASE_URL              = "https://royalottawagolfclub.teetimes.totalclubunity.com"
        PLAY_DAY              = int(cfg.get("play_day", 1))
        buddies               = cfg.get("buddies", [])
        BUDDIES               = [b["name"] for b in buddies]
        BUDDY_USER_IDS        = {b["name"]: b["user_id"] for b in buddies}
        # Redirect file outputs to data/ alongside scheduled_runner
        data_dir              = Path(cfg["data_dir"])
        SCREENSHOTS           = data_dir / "screenshots"
        RAW_JSON_FILE         = data_dir / "tee_times_raw.json"
        SCREENSHOTS.mkdir(exist_ok=True)

    TZ = ZoneInfo(TIMEZONE)

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent
SCREENSHOTS    = BASE_DIR / "screenshots"
LOG_FILE       = BASE_DIR / "booking.log"
RAW_JSON_FILE  = BASE_DIR / "tee_times_raw.json"
SCREENSHOTS.mkdir(exist_ok=True)

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

TZ = ZoneInfo(TIMEZONE)


# ── Date helpers ─────────────────────────────────────────────────────────────

def get_next_tuesday():
    """Return the date of the next Tuesday (legacy — use get_next_play_day)."""
    return get_next_play_day(1)

def get_next_play_day(play_day: int = 1):
    """Return the date of the next occurrence of play_day (0=Mon, 1=Tue, ..., 6=Sun)."""
    today = datetime.now(TZ).date()
    days_ahead = (play_day - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def fmt_date(d) -> str:
    """Format date as 'Tue, Jun 09 2026' for the tee-times API."""
    return d.strftime("%a, %b %d %Y")


def booking_open_time() -> datetime:
    """Today's 7:30:00 Eastern as a timezone-aware datetime."""
    now = datetime.now(TZ)
    return now.replace(
        hour=BOOKING_OPENS_HOUR, minute=BOOKING_OPENS_MINUTE,
        second=0, microsecond=0,
    )


# ── Playwright helpers ────────────────────────────────────────────────────────

async def ss(page: Page, name: str) -> Path:
    """Take a screenshot and return its path."""
    p = SCREENSHOTS / f"{name}.png"
    await page.screenshot(path=str(p), full_page=False)
    log.info(f"  screenshot -> {p.name}")
    return p


# ── Step 1: Login ─────────────────────────────────────────────────────────────

async def login(page: Page):
    log.info("LOGIN — navigating to /login")
    await page.goto(f"{BASE_URL}/users/login", wait_until="domcontentloaded")
    await ss(page, "01_login")

    await page.fill('input[name="email"]',    USERNAME)
    await page.fill('input[name="password"]', PASSWORD)

    async with page.expect_navigation(wait_until="domcontentloaded"):
        await page.click('input[type="submit"], button.login_btn')

    log.info(f"  URL after login: {page.url}")
    if "/users/login" in page.url:
        await ss(page, "error_login_failed")
        raise RuntimeError("Login failed — check USERNAME / PASSWORD in config.py")

    await ss(page, "02_after_login")
    log.info("  Logged in OK")


# ── Step 2: Navigate to booking / select event ────────────────────────────────

async def navigate_to_booking(page: Page):
    log.info("BOOKING — selecting event, then /booking")
    # Silently select the event (sets server-side session variable).
    # The response is the changeevent page itself; we don't need to render it.
    await page.request.get(f"{BASE_URL}/changeevent/{COURSE_EVENT_ID}/")
    await page.goto(f"{BASE_URL}/booking", wait_until="domcontentloaded")
    log.info(f"  URL: {page.url}")
    await ss(page, "03_booking_page")


# ── Step 3: Fetch tee times ───────────────────────────────────────────────────

async def fetch_tee_times(page: Page, date_str: str) -> dict | list:
    url = (
        f"{BASE_URL}/booking/teetimes/"
        f"?date={date_str}&holes=any&players=any&time_of_day=any&course_id="
    )
    log.info(f"FETCH — {url}")
    t0 = _time.perf_counter()
    resp: Response = await page.request.get(url)
    elapsed = _time.perf_counter() - t0

    body = await resp.body()
    log.info(f"  {resp.status}  {len(body)//1024} KB  {elapsed*1000:.0f} ms")

    if not resp.ok:
        raise RuntimeError(f"Tee-times request failed: {resp.status}")

    raw_text = body.decode("utf-8", errors="replace")
    RAW_JSON_FILE.write_text(raw_text, encoding="utf-8")

    return json.loads(raw_text)


# ── Step 4: Parse JSON, find best slot ───────────────────────────────────────

def _slot_local_time(slot: dict) -> str:
    """
    Return the slot's local time as a string like '8:00 AM'.
    Uses the 'teedatetime' ISO field confirmed by recon.
    """
    raw = slot.get("teedatetime", "")
    if not raw:
        return ""
    dt = datetime.fromisoformat(raw).astimezone(TZ)
    h  = dt.hour % 12 or 12
    return "%d:%02d %s" % (h, dt.minute, "AM" if dt.hour < 12 else "PM")


def _pref_key(t: str) -> str:
    """'8:00 AM' normalised: strip leading zero, uppercase."""
    t = t.strip().upper()
    if t and t[0] == "0":
        t = t[1:]
    return t


def find_best_slot(data: dict | list) -> dict | None:
    """
    Parse the tee-times payload and return the best available, bookable slot.

    Confirmed field names (from recon on 2026-06-02):
      teedatetime     — ISO datetime string  e.g. "2026-06-09T08:00:00-04:00"
      available_spots — integer              e.g. 4
      bookable        — boolean              True once booking window is open
      id              — integer slot ID      e.g. 167992
    """
    slots: list = data.get("teetimes", []) if isinstance(data, dict) else data

    log.info(f"  Total slots in payload: {len(slots)}")
    if not slots:
        return None

    # Build time -> [slot, ...] index
    by_time: dict[str, list] = {}
    for slot in slots:
        key = _pref_key(_slot_local_time(slot))
        by_time.setdefault(key, []).append(slot)

    bookable_found   = 0
    unavailable_full = 0

    for pref in PREFERRED_TIMES:
        key        = _pref_key(pref)
        candidates = by_time.get(key, [])
        for slot in candidates:
            sid       = slot.get("id")
            avail     = slot.get("available_spots", 0)
            ok        = slot.get("bookable", False)
            reason    = slot.get("bookable_reason", "")
            course_id = slot.get("course_id")

            # Hard filter: only book the configured course (Main Course = 1)
            if course_id != COURSE_JSON_ID:
                log.info(f"  SKIP (course_id={course_id}, want {COURSE_JSON_ID}): {pref}  id={sid}")
                continue

            if ok and avail >= 4 and sid:
                log.info(f"  BOOKABLE: {pref}  id={sid}  spots={avail}  course_id={course_id}")
                return {"id": sid, "time": pref, "raw": slot}
            elif not ok:
                bookable_found += 1
                log.info(f"  NOT YET BOOKABLE: {pref}  id={sid}  reason={reason!r}")
            else:
                unavailable_full += 1
                log.info(f"  FULL: {pref}  id={sid}  spots={avail}")

    if bookable_found > 0:
        log.warning(
            f"  {bookable_found} preferred slots exist but bookable=False "
            f"(booking window not open yet?)"
        )
    return None


# ── Step 5: Place hold ────────────────────────────────────────────────────────

async def place_hold(page: Page, teetime_id: int | str):
    url = f"{BASE_URL}/booking/checkholds/{teetime_id}/"
    log.info(f"HOLD — {url}")
    t0 = _time.perf_counter()
    resp = await page.request.get(url)
    log.info(f"  {resp.status}  {(_time.perf_counter()-t0)*1000:.0f} ms")
    if not resp.ok:
        raise RuntimeError(f"Hold failed: {resp.status}")


# ── Step 6: Navigate to details page ─────────────────────────────────────────

async def navigate_to_details(page: Page, teetime_id: int | str):
    url = f"{BASE_URL}/booking/details/{teetime_id}/{COURSE_URL_ID}/any/?groups=1"
    log.info(f"DETAILS — {url}")
    await page.goto(url, wait_until="domcontentloaded")
    await ss(page, "04_details_page")


# ── Step 7: Add golfers via Buddy Group ──────────────────────────────────────
#
# Confirmed from recon (2026-06-02):
#   - The "Add Golfer" panel is a hidden div, NOT a modal.
#   - There's a "Buddy Group" tab with "Tuesday Morning Group" (id=73)
#     containing all 3 buddies: Sojonky (1107), Doyle (338), Brooks (150).
#   - Selecting the group and clicking "Add Buddy Group" triggers 3 sequential
#     AJAX calls to /booking/teetimedetails/{user}/{teetime}/{buddy_id}/false,
#     then adds hidden <input name="booking-users[]"> for each buddy.
#   - The panel auto-closes when max_players (4) is reached.

async def add_golfers(page: Page, _buddies: list[str]):
    log.info("GOLFERS — adding via Tuesday Morning Group (buddy group)")

    # 1. Open the add-golfer panel
    await page.click(".btn-add-golfer")

    # 2. Switch to the Buddy Group tab
    await page.click("#buddy-group-tab")

    # 3. Select "Tuesday Morning Group" (value=73) from the dropdown
    await page.select_option(".add-buddy-group", BUDDY_GROUP_ID)
    log.info(f"  Selected buddy group id={BUDDY_GROUP_ID}")

    # 4. Click "Add Buddy Group" to trigger the AJAX calls
    t0 = _time.perf_counter()
    await page.click(".btn-submit-golfer")

    # 5. Wait until all 3 buddies are added (4 booking-users inputs = Martin + 3)
    try:
        await page.wait_for_function(
            "document.querySelectorAll('input.booking-users').length >= 4",
            timeout=12_000,
        )
        elapsed = _time.perf_counter() - t0
        log.info(f"  All golfers added in {elapsed*1000:.0f} ms")
    except Exception:
        # Fallback: add buddies one by one from the Buddy List dropdown
        log.warning("  Buddy Group timed out — falling back to individual buddy selection")
        await _add_golfers_individually(page)

    await ss(page, "05_golfers_added")


async def _add_golfers_individually(page: Page):
    """Fallback: add each buddy one at a time via the Buddy List select."""
    for name, uid in BUDDY_USER_IDS.items():
        log.info(f"  Adding individually: {name} (id={uid})")
        # Re-open the panel if it closed
        if await page.locator(".btn-add-golfer").is_visible():
            await page.click(".btn-add-golfer")
        # Ensure we're on the Buddy List tab (default)
        await page.click("#buddy-tab")
        # Select this buddy by their user ID value
        await page.select_option(".add-buddy", str(uid))
        await page.click(".btn-submit-golfer")
        # Wait for this buddy's input to appear
        await asyncio.sleep(1.0)


# ── Step 8: Submit the booking ────────────────────────────────────────────────

async def submit_booking(page: Page):
    # Book Now triggers onclick="payAtCourse(); return false;"
    # payAtCourse() calls $("#booking-form").submit() which causes a full navigation.
    # We wait for the receipt URL rather than using expect_navigation.
    log.info("SUBMIT — clicking Book Now (.book-now-btn)")

    await page.click(".book-now-btn")
    try:
        await page.wait_for_url("**/booking/receipt/**", timeout=8_000)
        log.info("  Receipt URL reached via approach 1 (click)")
    except Exception:
        log.warning("  No receipt URL after click — trying payAtCourse() directly")
        await page.evaluate("payAtCourse()")
        try:
            await page.wait_for_url("**/booking/receipt/**", timeout=8_000)
            log.info("  Receipt URL reached via approach 2 (evaluate)")
        except Exception:
            log.warning("  Still no receipt URL — trying dispatch_event")
            await page.locator(".book-now-btn").dispatch_event("click")
            await page.wait_for_url("**/booking/receipt/**", timeout=10_000)
            log.info("  Receipt URL reached via approach 3 (dispatch_event)")

    await ss(page, "06_after_submit")


# ── Step 9: Verify success ────────────────────────────────────────────────────

async def verify_success(page: Page) -> bool:
    log.info(f"VERIFY — URL: {page.url}")
    if "/booking/receipt/" in page.url:
        content = await page.content()
        if "Booking Confirmation" in content or "confirmed" in content.lower():
            await ss(page, "07_CONFIRMED")
            log.info("SUCCESS — booking confirmed!")
            return True

    log.error(f"Did not reach receipt page. URL: {page.url}")
    await ss(page, "error_unexpected_page_after_submit")
    return False


# ── Timing: wait until 7:30:00.000 AM ────────────────────────────────────────

async def wait_until_open(page: Page):
    """Sleep until booking opens, with keep-alive pings and a tight loop for the final 2s."""
    target = booking_open_time()
    now    = datetime.now(TZ)

    if now >= target:
        log.info("Booking window already open — proceeding immediately")
        return

    secs = (target - now).total_seconds()
    log.info(f"Waiting until {target.strftime('%H:%M:%S %Z')} — {secs:.1f}s from now")

    # Coarse wait with keep-alive pings every 60s to prevent session expiry
    while True:
        remaining = (target - datetime.now(TZ)).total_seconds()
        if remaining <= 2.5:
            break
        sleep_for = min(60.0, remaining - 2.0)
        await asyncio.sleep(sleep_for)
        try:
            await page.goto(f"{BASE_URL}/booking", wait_until="domcontentloaded")
            log.info(f"  [keep-alive] /booking — {(target - datetime.now(TZ)).total_seconds():.0f}s remaining")
        except Exception as e:
            log.warning(f"  [keep-alive] ping failed: {e}")

    # Tight polling loop for precision
    log.info("Entering tight loop...")
    while datetime.now(TZ) < target:
        await asyncio.sleep(0.001)

    fire_time = datetime.now(TZ)
    log.info(f"GO — {fire_time.strftime('%H:%M:%S.%f %Z')}")


# ── Orchestrator ──────────────────────────────────────────────────────────────

async def run(args):
    dry_run     = args.dry_run
    headless    = not args.show_browser
    do_wait     = args.wait
    target_date = args.date or fmt_date(get_next_play_day(PLAY_DAY))

    log.info("=" * 60)
    log.info("Royal Ottawa Golf Club — Tee Time Booker")
    log.info(f"Target date  : {target_date}")
    log.info(f"Dry run      : {dry_run}")
    log.info(f"Headless     : {headless}")
    log.info(f"Wait for open: {do_wait}")
    log.info("=" * 60)

    async with async_playwright() as pw:
        browser: Browser = await pw.firefox.launch(headless=headless)
        ctx: BrowserContext = await browser.new_context()
        page: Page = await ctx.new_page()

        try:
            # ── Pre-game: login + navigate BEFORE 7:30 AM ────────────────
            await login(page)
            await navigate_to_booking(page)

            # ── Wait until 7:30:00.000 AM (skipped for dry-run) ──────────
            if do_wait and not dry_run:
                await wait_until_open(page)

            # ── Fetch tee times + find bookable slot ──────────────────────
            # At exactly 7:30 AM the server flips bookable=True. Retry up
            # to 5s in live mode; dry-run does a single fetch and reports.
            t_start      = _time.perf_counter()
            slot         = None
            max_attempts = 1 if dry_run else 18   # 18 × 300 ms ≈ 5.4 s max
            for attempt in range(max_attempts):
                data = await fetch_tee_times(page, target_date)
                slot = find_best_slot(data)
                if slot:
                    break
                if dry_run:
                    break
                elapsed_so_far = _time.perf_counter() - t_start
                if elapsed_so_far > 5.0:
                    break
                log.info(f"  No bookable slot yet — retry {attempt+1} in 300 ms")
                await asyncio.sleep(0.3)

            if not slot:
                if dry_run:
                    log.info("[DRY RUN] Flow OK — no bookable slot right now (normal outside the window)")
                    return True
                log.error("No preferred tee times available after retries. Check tee_times_raw.json.")
                await ss(page, "error_no_slots")
                return False

            teetime_id = slot["id"]
            log.info(f"Selected: {slot['time']}  id={teetime_id}")

            if dry_run:
                elapsed = _time.perf_counter() - t_start
                log.info(f"[DRY RUN] Would book {slot['time']} — stopping ({elapsed:.2f}s so far)")
                return True

            # ── Place hold ────────────────────────────────────────────────
            await place_hold(page, teetime_id)

            # ── Details page ──────────────────────────────────────────────
            await navigate_to_details(page, teetime_id)

            # ── Add golfers ───────────────────────────────────────────────
            await add_golfers(page, BUDDIES)

            # ── Submit ────────────────────────────────────────────────────
            await submit_booking(page)

            # ── Verify ────────────────────────────────────────────────────
            success = await verify_success(page)

            elapsed = _time.perf_counter() - t_start
            log.info(f"Total time from 7:30 AM: {elapsed:.2f}s")
            return success

        except Exception as exc:
            log.error(f"FATAL: {exc}", exc_info=True)
            try:
                await ss(page, "fatal_error")
            except Exception:
                pass
            return False

        finally:
            await ctx.close()
            await browser.close()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Royal Ottawa Golf Club automated tee-time booker"
    )
    p.add_argument(
        "--wait", action="store_true",
        help="Sleep until 7:30 AM Eastern, then fire the booking",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Do everything except the final booking confirmation POST",
    )
    p.add_argument(
        "--show-browser", action="store_true",
        help="Show the browser window (default: headless)",
    )
    p.add_argument(
        "--date", type=str, default=None,
        help="Override target date, e.g. 'Tue, Jun 09 2026'",
    )
    args = p.parse_args()
    load_config("file")
    success = asyncio.run(run(args))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
