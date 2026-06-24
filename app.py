import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from werkzeug.security import generate_password_hash, check_password_hash

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from markupsafe import Markup

from database import init_db, get_db
from crypto import encrypt, decrypt

# ── App factory ────────────────────────────────────────────────────────────────

app = Flask(__name__)
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
(DATA_DIR / "screenshots").mkdir(exist_ok=True)

SECRET_KEY_FILE = DATA_DIR / ".secret_key"
if SECRET_KEY_FILE.exists():
    app.secret_key = SECRET_KEY_FILE.read_bytes()
else:
    key = os.urandom(32)
    SECRET_KEY_FILE.write_bytes(key)
    app.secret_key = key

init_db()

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
BUDDY_COLORS = ["#1E3A2C", "#7A4B1E", "#3B4C7A", "#6B2E4E", "#2C5840", "#5A4B7A"]
TIME_OPTS = [
    "6:30 AM", "6:40 AM", "6:50 AM",
    "7:00 AM", "7:10 AM", "7:20 AM", "7:30 AM", "7:40 AM", "7:50 AM",
    "8:00 AM", "8:10 AM", "8:20 AM", "8:30 AM", "8:40 AM", "8:50 AM",
    "9:00 AM", "9:10 AM", "9:20 AM", "9:30 AM",
]

# ── SVG icon system ────────────────────────────────────────────────────────────

_SVGS = {
    'flag':     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><path d="M5 21V4M5 4l11 2.5-4 3 4 3L5 16"/></svg>',
    'tee':      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><circle cx="12" cy="6.5" r="3.5"/><path d="M9.6 9.3 8 21M14.4 9.3 16 21M6.5 21h11"/></svg>',
    'clock':    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><circle cx="12" cy="12" r="9"/><path d="M12 7.5V12l3 2"/></svg>',
    'calendar': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/></svg>',
    'bolt':     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z"/></svg>',
    'check':    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><path d="M4 12.5 9.5 18 20 6.5"/></svg>',
    'cross':    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><path d="M6 6l12 12M18 6 6 18"/></svg>',
    'triangle': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><path d="M12 4 22 20H2L12 4Z"/><path d="M12 10v4.5M12 17.5h.01"/></svg>',
    'pause':    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" width="{w}" height="{h}" style="{s}"><path d="M9 5v14M15 5v14"/></svg>',
    'arrowUp':  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><path d="M12 19V5M6 11l6-6 6 6"/></svg>',
    'arrowDown':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><path d="M12 5v14M18 13l-6 6-6-6"/></svg>',
    'plus':     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><path d="M12 5v14M5 12h14"/></svg>',
    'trash':    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><path d="M4 7h16M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13"/></svg>',
    'grip':     '<svg viewBox="0 0 24 24" fill="currentColor" width="{w}" height="{h}" style="{s}"><circle cx="9" cy="6" r="1.6"/><circle cx="15" cy="6" r="1.6"/><circle cx="9" cy="12" r="1.6"/><circle cx="15" cy="12" r="1.6"/><circle cx="9" cy="18" r="1.6"/><circle cx="15" cy="18" r="1.6"/></svg>',
    'edit':     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><path d="M4 20h4L19 9l-4-4L4 16v4ZM14 6l4 4"/></svg>',
    'bell':     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6M10 20a2 2 0 0 0 4 0"/></svg>',
    'shield':   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><path d="M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6l-7-3Z"/></svg>',
    'lock':     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>',
    'users':    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><circle cx="9" cy="8" r="3"/><path d="M3 19c0-3 2.5-5 6-5s6 2 6 5"/><path d="M16 6a3 3 0 0 1 0 6M17.5 14c2.5 0 4.5 2 4.5 5"/></svg>',
    'refresh':  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><path d="M20 11a8 8 0 0 0-14-4M4 5v4h4M4 13a8 8 0 0 0 14 4M20 19v-4h-4"/></svg>',
    'image':    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><rect x="3.5" y="5" width="17" height="14" rx="2.5"/><circle cx="8.5" cy="10" r="1.6"/><path d="M21 16l-5-5L5 19"/></svg>',
    'external': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><path d="M14 5h5v5M19 5l-8 8M11 5H6a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5"/></svg>',
    'info':     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5h.01"/></svg>',
    'eye':      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="2.8"/></svg>',
    'signout':  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><path d="M14 7V5a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2v-2M9 12h11M17 9l3 3-3 3"/></svg>',
    'globe':    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.5 2.5 15 0 18M12 3c-2.5 2.5-2.5 15 0 18"/></svg>',
    'list':     '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/></svg>',
    'target':   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" width="{w}" height="{h}" style="{s}"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.4" fill="currentColor"/></svg>',
}

def ic(name, size=17, style=''):
    svg = _SVGS.get(name, '')
    return Markup(svg.format(w=size, h=size, s=style))

def fmt_date(d):
    return d.strftime('%a %b') + ' ' + str(d.day)

app.jinja_env.globals['ic'] = ic
app.jinja_env.globals['enumerate'] = enumerate
app.jinja_env.globals['fmt_date'] = fmt_date

# ── DB helpers ─────────────────────────────────────────────────────────────────

def get_config():
    with get_db() as conn:
        row = conn.execute("SELECT * FROM config WHERE id = 1").fetchone()
        return dict(row) if row else {}

def update_config(**kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [1]
    with get_db() as conn:
        conn.execute(f"UPDATE config SET {sets} WHERE id = ?", vals)
        conn.commit()

def get_preferred_times():
    cfg = get_config()
    try:
        return json.loads(cfg.get('preferred_times') or '[]')
    except Exception:
        return []

def get_buddies():
    with get_db() as conn:
        return conn.execute("SELECT * FROM buddies ORDER BY sort_order, id").fetchall()

# ── Auth ───────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        cfg = get_config()
        if not cfg.get('setup_complete'):
            return redirect(url_for('setup'))
        if not session.get('logged_in') or not session.get('username'):
            session.clear()
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

# ── Context processor ──────────────────────────────────────────────────────────

@app.context_processor
def inject_globals():
    cfg = get_config()
    has_pic = bool(cfg.get('profile_picture') and (DATA_DIR / cfg['profile_picture']).exists())
    return {
        'request_endpoint': request.endpoint,
        'logged_in': session.get('logged_in', False),
        'current_user': session.get('username', ''),
        'current_role': session.get('role', 'user'),
        'profile_picture_url': url_for('serve_profile_picture') if has_pic else None,
    }

# ── Scheduling helpers ─────────────────────────────────────────────────────────

def _ordinal(n):
    s = ["th", "st", "nd", "rd"]
    v = n % 100
    return str(n) + (s[(v - 20) % 10] if (v - 20) % 10 < len(s) else s[v] if v < len(s) else s[0])

def get_next_booking_info(cfg):
    """Return (run_date, target_date) as datetime objects."""
    tz = ZoneInfo(cfg.get('timezone', 'America/Toronto'))
    now = datetime.now(tz)
    play_day = cfg.get('play_day', 1)         # 0=Mon, 1=Tue
    bh = cfg.get('booking_opens_hour', 7)
    bm = cfg.get('booking_opens_min', 30)
    booking_dow = (play_day + 1) % 7          # booking runs day after play day (prev week)

    days_ahead = (booking_dow - now.weekday()) % 7
    if days_ahead == 0:
        run_today = now.replace(hour=bh, minute=bm, second=0, microsecond=0)
        if now >= run_today:
            days_ahead = 7

    run_date = (now + timedelta(days=days_ahead)).replace(
        hour=bh, minute=bm, second=0, microsecond=0
    )
    target_date = run_date + timedelta(days=6)
    return run_date, target_date

# ── Routes: Auth ───────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    cfg = get_config()
    if not cfg.get('setup_complete'):
        return redirect(url_for('setup'))
    if session.get('logged_in') and session.get('username'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        with get_db() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['logged_in'] = True
            session['user_id']   = user['id']
            session['username']  = user['username']
            session['role']      = user['role']
            session.permanent    = True
            if user['must_change_password']:
                return redirect(url_for('account_setup'))
            return redirect(url_for('dashboard'))
        flash('Incorrect username or password.', 'error')

    return render_template('login.html')


@app.route('/account/setup', methods=['GET', 'POST'])
def account_setup():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (session.get('user_id'),)).fetchone()
    if not user or not user['must_change_password']:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        new_username = request.form.get('username', '').strip()
        new_password = request.form.get('password', '')
        confirm      = request.form.get('confirm', '')
        if not new_username:
            flash('Username cannot be empty.', 'error')
        elif len(new_password) < 6:
            flash('Password must be at least 6 characters.', 'error')
        elif new_password != confirm:
            flash('Passwords do not match.', 'error')
        else:
            with get_db() as conn:
                taken = conn.execute(
                    "SELECT id FROM users WHERE username = ? AND id != ?",
                    (new_username, session['user_id'])
                ).fetchone()
                if taken:
                    flash('That username is already taken.', 'error')
                else:
                    conn.execute(
                        "UPDATE users SET username=?, password_hash=?, must_change_password=0 WHERE id=?",
                        (new_username, generate_password_hash(new_password), session['user_id'])
                    )
                    conn.commit()
            session['username'] = new_username
            flash('Account set up. Welcome!', 'success')
            return redirect(url_for('dashboard'))

    return render_template('account_setup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    cfg = get_config()
    if cfg.get('setup_complete'):
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        golf_user = request.form.get('golf_username', '').strip()
        golf_pw   = request.form.get('golf_password', '')

        if not golf_user:
            flash('Golf club email is required.', 'error')
        else:
            update_config(
                golf_username=golf_user,
                golf_password_enc=encrypt(golf_pw) if golf_pw else '',
                setup_complete=1,
            )
            with get_db() as conn:
                buddies_data = [
                    ("Hugh Doyle",    338,  "#7A4B1E", 0),
                    ("Patrick Brooks", 150, "#3B4C7A", 1),
                    ("Andrew Sojonky", 1107,"#6B2E4E", 2),
                ]
                conn.executemany(
                    "INSERT OR IGNORE INTO buddies (name, user_id, color, sort_order) VALUES (?,?,?,?)",
                    buddies_data
                )
                conn.commit()

            session['logged_in'] = True
            flash('Setup complete. Welcome to The Tuesday Man.', 'success')
            return redirect(url_for('dashboard'))

    return render_template('setup.html')

# ── Routes: Profile picture ────────────────────────────────────────────────────

ALLOWED_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

@app.route('/profile-picture')
def serve_profile_picture():
    cfg = get_config()
    filename = cfg.get('profile_picture')
    if not filename:
        return '', 404
    path = DATA_DIR / filename
    if not path.exists():
        return '', 404
    return send_file(path)

@app.route('/settings/profile-picture', methods=['POST'])
@login_required
def settings_profile_picture():
    file = request.files.get('photo')
    if not file or not file.filename:
        flash('No file selected.', 'error')
        return redirect(url_for('settings') + '#profile')

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        flash('Please upload a JPG, PNG, GIF, or WebP image.', 'error')
        return redirect(url_for('settings') + '#profile')

    # Remove old file if different extension
    cfg = get_config()
    old = cfg.get('profile_picture')
    if old and old != f'profile{ext}':
        (DATA_DIR / old).unlink(missing_ok=True)

    filename = f'profile{ext}'
    file.save(DATA_DIR / filename)
    update_config(profile_picture=filename)
    flash('Profile photo updated.', 'success')
    return redirect(url_for('settings') + '#profile')

@app.route('/settings/profile-picture/remove', methods=['POST'])
@login_required
def settings_profile_picture_remove():
    cfg = get_config()
    if cfg.get('profile_picture'):
        (DATA_DIR / cfg['profile_picture']).unlink(missing_ok=True)
        update_config(profile_picture=None)
    flash('Profile photo removed.', 'success')
    return redirect(url_for('settings') + '#profile')

# ── Routes: Dashboard ──────────────────────────────────────────────────────────

@app.route('/')
@login_required
def dashboard():
    cfg = get_config()
    times = get_preferred_times()
    buddies = get_buddies()
    run_date, target_date = get_next_booking_info(cfg)

    with get_db() as conn:
        recent_logs = conn.execute(
            "SELECT * FROM booking_log ORDER BY timestamp DESC LIMIT 5"
        ).fetchall()
        last_run = conn.execute(
            "SELECT * FROM inspector_runs ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()

    bh = cfg.get('booking_opens_hour', 7)
    bm = cfg.get('booking_opens_min', 30)
    ampm = 'AM' if bh < 12 else 'PM'
    h12 = bh % 12 or 12

    return render_template('dashboard.html',
        cfg=cfg, times=times, buddies=buddies,
        run_date=run_date, target_date=target_date,
        recent_logs=recent_logs, last_inspector=last_run,
        opens_str=f"{h12}:{bm:02d} {ampm}",
        ordinal=_ordinal,
    )

@app.route('/api/run-now', methods=['POST'])
@login_required
def run_now():
    runner = Path(__file__).parent / 'scheduled_runner.py'
    try:
        subprocess.run(
            [sys.executable, str(runner), '--dry-run'],
            capture_output=True, text=True, timeout=120,
            cwd=str(Path(__file__).parent),
        )
    except subprocess.TimeoutExpired:
        return jsonify({'status': 'error', 'message': 'Dry run timed out after 120s.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM booking_log ORDER BY id DESC LIMIT 1"
        ).fetchone()

    if row:
        status = row['status']
        msg = status
        if row['target_date']:
            msg += f" — {row['target_date']}"
        if row['target_time']:
            msg += f" at {row['target_time']}"
        if row['duration_ms']:
            msg += f" ({row['duration_ms']} ms)"
        return jsonify({'status': status.lower(), 'message': msg})

    return jsonify({'status': 'done', 'message': 'Dry run complete — no log entry found.'})

# ── Routes: Settings ───────────────────────────────────────────────────────────

@app.route('/settings')
@login_required
def settings():
    cfg = get_config()
    times = get_preferred_times()
    return render_template('settings.html', cfg=cfg, times=times,
                           days=DAYS_OF_WEEK, time_opts=TIME_OPTS)

@app.route('/settings/booking', methods=['POST'])
@login_required
def settings_booking():
    update_config(booking_active=1 if request.form.get('booking_active') else 0)
    flash('Booking status updated.', 'success')
    return redirect(url_for('settings') + '#booking')

@app.route('/settings/credentials', methods=['POST'])
@login_required
def settings_credentials():
    golf_user = request.form.get('golf_username', '').strip()
    golf_pw   = request.form.get('golf_password', '').strip()

    if not golf_user:
        flash('Golf club email cannot be empty.', 'error')
        return redirect(url_for('settings') + '#credentials')

    updates = {'golf_username': golf_user}
    if golf_pw:
        updates['golf_password_enc'] = encrypt(golf_pw)
    update_config(**updates)
    flash('Credentials saved.', 'success')
    return redirect(url_for('settings') + '#credentials')

@app.route('/settings/schedule', methods=['POST'])
@login_required
def settings_schedule():
    try:
        play_day = int(request.form.get('play_day', 1))
        hour_raw = int(request.form.get('opens_hour', 7))
        minute   = int(request.form.get('opens_min', 30))
        ampm     = request.form.get('opens_ampm', 'AM')
        if ampm == 'PM' and hour_raw < 12:
            hour_raw += 12
        elif ampm == 'AM' and hour_raw == 12:
            hour_raw = 0
    except ValueError:
        flash('Invalid schedule values.', 'error')
        return redirect(url_for('settings') + '#schedule')

    update_config(play_day=play_day, booking_opens_hour=hour_raw, booking_opens_min=minute)
    flash('Schedule saved.', 'success')
    return redirect(url_for('settings') + '#schedule')

@app.route('/settings/notifications', methods=['POST'])
@login_required
def settings_notifications():
    update_config(
        notification_email=request.form.get('notification_email', '').strip(),
        notify_success=1  if request.form.get('notify_success')  else 0,
        notify_fallback=1 if request.form.get('notify_fallback') else 0,
        notify_failure=1  if request.form.get('notify_failure')  else 0,
        notify_drift=1    if request.form.get('notify_drift')    else 0,
        notify_weekly=1   if request.form.get('notify_weekly')   else 0,
    )
    flash('Notification preferences saved.', 'success')
    return redirect(url_for('settings') + '#notifications')

@app.route('/settings/course', methods=['POST'])
@login_required
def settings_course():
    try:
        cjid = int(request.form.get('course_json_id', 1) or 1)
        mid  = int(request.form.get('martin_user_id', 755) or 755)
    except ValueError:
        flash('Invalid course settings.', 'error')
        return redirect(url_for('settings') + '#course')
    update_config(
        course_event_id=request.form.get('course_event_id', '2079').strip(),
        course_url_id=request.form.get('course_url_id', '27').strip(),
        course_json_id=cjid,
        buddy_group_id=request.form.get('buddy_group_id', '73').strip(),
        martin_user_id=mid,
    )
    flash('Course settings saved.', 'success')
    return redirect(url_for('settings') + '#course')

# Preferred times CRUD
@app.route('/settings/times/add', methods=['POST'])
@login_required
def times_add():
    new_time = request.form.get('new_time', '').strip()
    times = get_preferred_times()
    if new_time and new_time not in times and len(times) < 8:
        times.append(new_time)
        update_config(preferred_times=json.dumps(times))
    return redirect(url_for('settings') + '#times')

@app.route('/settings/times/remove/<int:idx>', methods=['POST'])
@login_required
def times_remove(idx):
    times = get_preferred_times()
    if 0 <= idx < len(times) and len(times) > 1:
        times.pop(idx)
        update_config(preferred_times=json.dumps(times))
    return redirect(url_for('settings') + '#times')

@app.route('/settings/times/move/<int:idx>/<direction>', methods=['POST'])
@login_required
def times_move(idx, direction):
    times = get_preferred_times()
    if direction == 'up' and 0 < idx < len(times):
        times[idx], times[idx - 1] = times[idx - 1], times[idx]
    elif direction == 'down' and 0 <= idx < len(times) - 1:
        times[idx], times[idx + 1] = times[idx + 1], times[idx]
    update_config(preferred_times=json.dumps(times))
    return redirect(url_for('settings') + '#times')

# ── Routes: Buddies ────────────────────────────────────────────────────────────

@app.route('/buddies')
@login_required
def buddies():
    return render_template('buddies.html', buddies=get_buddies())

@app.route('/buddies/add', methods=['POST'])
@login_required
def buddies_add():
    name    = request.form.get('name', '').strip()
    user_id = request.form.get('user_id', '').strip()

    if not name:
        flash('Buddy name is required.', 'error')
        return redirect(url_for('buddies'))

    current = get_buddies()
    if len(current) >= 3:
        flash('Foursome is full. Remove someone first.', 'error')
        return redirect(url_for('buddies'))

    color = BUDDY_COLORS[len(current) % len(BUDDY_COLORS)]
    with get_db() as conn:
        max_order = conn.execute("SELECT COALESCE(MAX(sort_order), -1) FROM buddies").fetchone()[0]
        conn.execute(
            "INSERT INTO buddies (name, user_id, color, sort_order) VALUES (?,?,?,?)",
            (name, int(user_id) if user_id.isdigit() else None, color, max_order + 1)
        )
        conn.commit()

    flash(f'Added {name}.', 'success')
    return redirect(url_for('buddies'))

@app.route('/buddies/remove/<int:buddy_id>', methods=['POST'])
@login_required
def buddies_remove(buddy_id):
    with get_db() as conn:
        conn.execute("DELETE FROM buddies WHERE id = ?", (buddy_id,))
        conn.commit()
    flash('Buddy removed.', 'success')
    return redirect(url_for('buddies'))

@app.route('/buddies/edit/<int:buddy_id>', methods=['POST'])
@login_required
def buddies_edit(buddy_id):
    name    = request.form.get('name', '').strip()
    user_id = request.form.get('user_id', '').strip()
    if not name:
        flash('Name cannot be empty.', 'error')
        return redirect(url_for('buddies'))
    with get_db() as conn:
        conn.execute(
            "UPDATE buddies SET name = ?, user_id = ? WHERE id = ?",
            (name, int(user_id) if user_id.isdigit() else None, buddy_id)
        )
        conn.commit()
    flash(f'Updated {name}.', 'success')
    return redirect(url_for('buddies'))

@app.route('/buddies/move/<int:buddy_id>/<direction>', methods=['POST'])
@login_required
def buddies_move(buddy_id, direction):
    with get_db() as conn:
        rows = conn.execute("SELECT id FROM buddies ORDER BY sort_order, id").fetchall()
        ids = [r['id'] for r in rows]
        if buddy_id not in ids:
            return redirect(url_for('buddies'))
        idx = ids.index(buddy_id)
        if direction == 'up' and idx > 0:
            ids[idx], ids[idx - 1] = ids[idx - 1], ids[idx]
        elif direction == 'down' and idx < len(ids) - 1:
            ids[idx], ids[idx + 1] = ids[idx + 1], ids[idx]
        for order, bid in enumerate(ids):
            conn.execute("UPDATE buddies SET sort_order = ? WHERE id = ?", (order, bid))
        conn.commit()
    return redirect(url_for('buddies'))

# ── Routes: Admin ─────────────────────────────────────────────────────────────

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    with get_db() as conn:
        users = conn.execute(
            "SELECT id, username, role, must_change_password FROM users ORDER BY id"
        ).fetchall()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/<int:user_id>/reset', methods=['POST'])
@login_required
@admin_required
def admin_reset_password(user_id):
    new_password = request.form.get('password', '').strip()
    if len(new_password) < 6:
        flash('Password must be at least 6 characters.', 'error')
        return redirect(url_for('admin_users'))
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET password_hash=?, must_change_password=1 WHERE id=?",
            (generate_password_hash(new_password), user_id)
        )
        conn.commit()
    flash('Password reset. User will be asked to change it on next login.', 'success')
    return redirect(url_for('admin_users'))

# ── Routes: Screenshots ────────────────────────────────────────────────────────

@app.route('/data/screenshots/<path:filename>')
@login_required
def serve_screenshot(filename):
    screenshots_dir = (DATA_DIR / 'screenshots').resolve()
    filepath = (screenshots_dir / filename).resolve()
    if not str(filepath).startswith(str(screenshots_dir)):
        return '', 403
    if not filepath.exists():
        return '', 404
    return send_file(filepath)

# ── Routes: Health ─────────────────────────────────────────────────────────────

@app.route('/health')
@login_required
def health():
    with get_db() as conn:
        runs = conn.execute(
            "SELECT * FROM inspector_runs ORDER BY timestamp DESC LIMIT 20"
        ).fetchall()
    return render_template('health.html', runs=runs)

@app.route('/api/run-inspector', methods=['POST'])
@login_required
def run_inspector():
    return jsonify({'status': 'stub', 'message': 'Phase 3: inspector coming next.'})

# ── Routes: Logs ───────────────────────────────────────────────────────────────

@app.route('/logs')
@login_required
def logs():
    page = max(1, int(request.args.get('page', 1)))
    per_page = 20
    offset = (page - 1) * per_page

    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM booking_log").fetchone()[0]
        log_rows = conn.execute(
            "SELECT * FROM booking_log ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (per_page, offset)
        ).fetchall()

    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template('logs.html', logs=log_rows, page=page,
                           total_pages=total_pages, total=total)

# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', '0') == '1', port=5000, host='0.0.0.0')
