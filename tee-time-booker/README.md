# Royal Ottawa Golf Club — Automated Tee Time Booker

Books Martin's Tuesday-morning round with his 3 buddies the moment slots open Wednesday at 7:00 AM Eastern.

## Setup (one time)

```bash
pip install playwright httpx
playwright install firefox
```

Fill in your credentials in **config.py**:
```python
USERNAME = "your_username"
PASSWORD = "your_password"
```

## Step 1 — Run recon first (important!)

The recon script logs in, fetches the live tee-times JSON, and dumps the field names
you need to verify the main script will parse correctly:

```bash
py recon.py --show-browser
```

This produces:
- `tee_times_raw.json` — full raw response (~500 KB)
- `details_page.html` — the booking-details form HTML
- `recon_summary.txt` — structured field map + XHR log

Check `recon_summary.txt`. If the JSON field names differ from what `book_tee_time.py`
expects, update the `find_best_slot()` helper in `book_tee_time.py` accordingly.

## Step 2 — Wednesday morning

```bash
# Run any time before 7 AM — logs in early, sleeps, fires at 7:00:00.000
py book_tee_time.py --wait

# Dry run (does everything except the final confirmation POST)
py book_tee_time.py --dry-run --wait

# Visible browser for debugging
py book_tee_time.py --show-browser
```

## What it does

| Time       | Action |
|------------|--------|
| ~6:55 AM   | Launches Firefox, logs in, navigates to booking page |
| 6:55–6:59  | Sits ready (pre-authenticated) |
| 7:00:00.000| Fires `GET /booking/teetimes/?date=…` |
| +0.1–0.3 s | Parses JSON, picks best available slot from preferred list |
| +0.4 s     | `GET /booking/checkholds/{id}/` — places hold |
| +0.6 s     | Navigates to `/booking/details/{id}/27/any/` |
| +1–2 s     | Adds 3 buddy golfers via Tagify UI |
| +2–3 s     | Clicks Book Now → verifies receipt page |

## Preferred tee times (config.py)

Tries in order: 8:00, 8:10, 8:20, 8:30, 8:40, 8:50 AM

## Golfers

- Martin McGarry (the logged-in user, user ID 755)
- Hugh Doyle
- Patrick Brooks
- Andrew Sojonky

## Output files

| File | Description |
|------|-------------|
| `booking.log` | Timestamped run log |
| `tee_times_raw.json` | Last fetched tee-times payload |
| `screenshots/` | PNG screenshots at every step + on errors |
| `recon_summary.txt` | From recon run |
| `details_page.html` | From recon run |

## Troubleshooting

**Login fails** — double-check `USERNAME` / `PASSWORD` in config.py.

**`find_best_slot` returns None** — open `tee_times_raw.json` and look at the actual field
names. Update the `slot.get("time")` fallback chain in `find_best_slot()`.

**Tagify input not found** — open `details_page.html` from the recon run and find the
correct selector. Update `_find_tagify_input()` in `book_tee_time.py`.

**Submit button not found** — same: inspect `details_page.html` and add the correct
selector to the `submit_booking()` list.

**All slots show as full at 7:00 AM** — the date string format may be wrong. Check the
`date` query param in `tee_times_raw.json` vs what the recon run shows.
