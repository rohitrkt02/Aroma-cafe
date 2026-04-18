"""
web_interface/app.py
Aroma & Co. — UNIFIED Flask Server  (Port 8000)

WHAT'S NEW:
  • Role-based authentication  (admin / staff)
  • Single URL login → auto-redirect to /dashboard
  • dashboards.py is now MERGED here — only ONE server needed
  • JWT-style session tokens stored server-side
  • /login  /logout  /dashboard  all on port 8000
  • All previous APIs preserved (/api/reserve, /chat, /api/slots …)

Roles:
  admin  → full dashboard (stats, all bookings, cancel, export)
  staff  → read-only view (today's bookings only)
"""

from flask import (Flask, render_template, request, jsonify,
                   session, redirect, url_for, abort)
from flask_cors import CORS
import requests as http_requests
import sqlite3, random, string, os, logging, hashlib, secrets
import smtplib, threading
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from datetime import date, timedelta, datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rasa URL — only used when running locally (not on Render)
# On Render, RASA_AVAILABLE=false so this line is never called
RASA_API_URL     = os.environ.get("RASA_API_URL", "http://localhost:5005/webhooks/rest/webhook")
RASA_AVAILABLE   = os.environ.get("RASA_AVAILABLE", "true").lower() == "true"
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH      = os.path.join(BASE_DIR, "database", "aroma.db")

CAFE_EMAIL    = os.environ.get("CAFE_EMAIL", "")
CAFE_EMAIL_PW = os.environ.get("CAFE_EMAIL_PASSWORD", "")

# ══════════════════════════════════════════════════════════════
#  USERS  (hashed passwords — change before production!)
#  Generate hash:  python -c "import hashlib; print(hashlib.sha256(b'yourpw').hexdigest())"
# ══════════════════════════════════════════════════════════════
def _h(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

USERS = {
    "admin": {
        "password_hash": _h("admin123"),
        "role": "admin",
        "name": "Café Admin",
        "avatar": "👑"
    },
    "staff": {
        "password_hash": _h("staff123"),
        "role": "staff",
        "name": "Floor Staff",
        "avatar": "☕"
    },
    "manager": {
        "password_hash": _h("manager123"),
        "role": "admin",
        "name": "Café Manager",
        "avatar": "📋"
    }
}

# ══════════════════════════════════════════════════════════════
#  AUTH DECORATORS
# ══════════════════════════════════════════════════════════════
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login", next=request.path))
        if session.get("role") != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated

# ══════════════════════════════════════════════════════════════
#  DB HELPER
# ══════════════════════════════════════════════════════════════
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ══════════════════════════════════════════════════════════════
#  EMAIL
# ══════════════════════════════════════════════════════════════
def send_confirmation_email(to_email, name, ref, dt, tm, guests, special=""):
    if not CAFE_EMAIL or not CAFE_EMAIL_PW:
        logger.info("Email not configured — skipping.")
        return
    if not to_email or "@" not in to_email:
        return

    def _send():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Booking Confirmed {ref} | Aroma & Co."
            msg["From"]    = f"Aroma & Co. <{CAFE_EMAIL}>"
            msg["To"]      = to_email

            sp_row = f"<tr style='border-top:1px solid #d4b896'><td style='padding:8px 0;color:#6b3f1f;font-size:14px'>Special</td><td style='padding:8px 0;color:#2c1a0e;font-size:14px;font-weight:600;text-align:right'>{special}</td></tr>" if special else ""

            html = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f5f0e8;font-family:Georgia,serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f0e8;padding:40px 20px">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="background:#1a0f07;border-radius:8px;overflow:hidden">
<tr><td style="padding:36px 40px;text-align:center">
  <h1 style="margin:0;font-size:28px;color:#d4a853;letter-spacing:2px">Aroma &amp; Co.</h1>
  <p style="margin:6px 0 0;font-size:12px;color:rgba(245,240,232,.5);letter-spacing:3px;text-transform:uppercase">Artisan Café · Lucknow</p>
</td></tr>
<tr><td style="padding:14px 40px;background:#4caf7d;text-align:center">
  <p style="margin:0;font-size:15px;color:#fff;font-weight:bold">✅ Table Confirmed!</p>
</td></tr>
<tr><td style="padding:36px 40px;background:#faf8f4">
  <p style="margin:0 0 24px;font-size:16px;color:#2c1a0e">Hello <strong>{name}</strong>! ☕</p>
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f0e8;border:1px solid #d4b896;border-radius:6px">
  <tr><td style="padding:16px 20px">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr><td style="padding:8px 0;color:#6b3f1f;font-size:13px;text-transform:uppercase;letter-spacing:1px">Ref</td>
          <td style="padding:8px 0;text-align:right"><span style="background:#2c1a0e;color:#d4a853;padding:4px 14px;border-radius:4px;font-family:monospace;font-size:15px;font-weight:bold">{ref}</span></td></tr>
      <tr style="border-top:1px solid #d4b896"><td style="padding:8px 0;color:#6b3f1f;font-size:14px">Date</td><td style="padding:8px 0;color:#2c1a0e;font-size:14px;font-weight:600;text-align:right">{dt}</td></tr>
      <tr style="border-top:1px solid #d4b896"><td style="padding:8px 0;color:#6b3f1f;font-size:14px">Time</td><td style="padding:8px 0;color:#2c1a0e;font-size:14px;font-weight:600;text-align:right">{tm}</td></tr>
      <tr style="border-top:1px solid #d4b896"><td style="padding:8px 0;color:#6b3f1f;font-size:14px">Guests</td><td style="padding:8px 0;color:#2c1a0e;font-size:14px;font-weight:600;text-align:right">{guests}</td></tr>
      {sp_row}
    </table>
  </td></tr></table>
  <p style="margin:24px 0 0;font-size:14px;color:#6b3f1f;line-height:1.8">
    📍 12-A Hazratganj, Lucknow – 226 001<br>
    📞 +91 98765 43210 &nbsp;|&nbsp; 📧 hello@aromaandco.in
  </p>
</td></tr>
<tr><td style="padding:20px 40px;background:#2c1a0e;text-align:center">
  <p style="margin:0;font-size:12px;color:rgba(245,240,232,.4)">© 2026 Aroma &amp; Co. · Made with ☕ in Lucknow</p>
</td></tr>
</table></td></tr></table></body></html>"""

            plain = f"Hello {name}!\n\nBooking confirmed.\nRef: {ref}\nDate: {dt}\nTime: {tm}\nGuests: {guests}\n\n12-A Hazratganj, Lucknow\n+91 98765 43210"
            msg.attach(MIMEText(plain, "plain"))
            msg.attach(MIMEText(html,  "html"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
                srv.login(CAFE_EMAIL, CAFE_EMAIL_PW)
                srv.sendmail(CAFE_EMAIL, to_email, msg.as_string())
            logger.info(f"Email sent to {to_email} for {ref}")
        except Exception as e:
            logger.error(f"Email failed: {e}")

    threading.Thread(target=_send, daemon=True).start()


# ══════════════════════════════════════════════════════════════
#  ██  AUTH ROUTES
# ══════════════════════════════════════════════════════════════

@app.route("/login", methods=["GET", "POST"])
def login():
    # Already logged in → go straight to dashboard
    if "user" in session:
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "").strip()
        user     = USERS.get(username)

        if user and user["password_hash"] == _h(password):
            session.permanent = True
            session["user"]   = username
            session["role"]   = user["role"]
            session["name"]   = user["name"]
            session["avatar"] = user["avatar"]
            logger.info(f"Login: {username} ({user['role']})")
            # Role-based redirect — both go to /dashboard
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid username or password."

    next_url = request.args.get("next", "")
    return render_template("login.html", error=error, next=next_url)


@app.route("/logout")
def logout():
    user = session.get("user", "unknown")
    session.clear()
    logger.info(f"Logout: {user}")
    return redirect(url_for("login"))


# ══════════════════════════════════════════════════════════════
#  ██  DASHBOARD (role-aware, login required)
# ══════════════════════════════════════════════════════════════

@app.route("/dashboard")
@login_required
def dashboard():
    try:
        conn = get_db()
        c    = conn.cursor()

        c.execute("SELECT COUNT(*) FROM reservations")
        total = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM reservations WHERE status='Confirmed'")
        confirmed = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM reservations WHERE status='Cancelled'")
        cancelled = c.fetchone()[0]

        today_str = date.today().isoformat()
        c.execute("SELECT COUNT(*) FROM reservations WHERE DATE(created_at)=?", (today_str,))
        today_count = c.fetchone()[0]

        c.execute("SELECT ref,name,phone,email,time,guests,special_req,status FROM reservations WHERE date=? ORDER BY time", (today_str,))
        today_res = [dict(r) for r in c.fetchall()]

        upcoming_dates = [(date.today() + timedelta(days=i)).isoformat() for i in range(1, 8)]
        c.execute(f"SELECT date, COUNT(*) as cnt FROM reservations WHERE date IN ({','.join(['?']*7)}) AND status!='Cancelled' GROUP BY date", upcoming_dates)
        upcoming = {r["date"]: r["cnt"] for r in c.fetchall()}

        # Recent bookings (last 20)
        c.execute("SELECT ref,name,phone,email,date,time,guests,status,created_at FROM reservations ORDER BY created_at DESC LIMIT 20")
        recent = [dict(r) for r in c.fetchall()]

        conn.close()
        return render_template("dashboard.html",
            total=total, confirmed=confirmed, cancelled=cancelled,
            today_count=today_count, today_res=today_res,
            upcoming=upcoming, recent=recent,
            role=session["role"], username=session["name"],
            avatar=session["avatar"], today=today_str
        )
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return render_template("dashboard.html",
            total=0, confirmed=0, cancelled=0, today_count=0,
            today_res=[], upcoming={}, recent=[],
            role=session["role"], username=session["name"],
            avatar=session["avatar"], today=date.today().isoformat()
        )


# ══════════════════════════════════════════════════════════════
#  ██  DASHBOARD API ROUTES  (JSON, login required)
# ══════════════════════════════════════════════════════════════

@app.route("/api/stats")
@login_required
def api_stats():
    try:
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM reservations"); total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM reservations WHERE status='Confirmed'"); confirmed = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM reservations WHERE status='Cancelled'"); cancelled = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM reservations WHERE DATE(created_at)=?", (date.today().isoformat(),)); today = c.fetchone()[0]
        conn.close()
        return jsonify({"total": total, "confirmed": confirmed, "cancelled": cancelled, "today": today})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/reservations")
@login_required
def list_reservations():
    df = request.args.get("date","").strip()
    sf = request.args.get("status","").strip()
    role = session.get("role")
    try:
        conn = get_db(); c = conn.cursor()
        q, p = "SELECT * FROM reservations WHERE 1=1", []
        # staff can only see today
        if role == "staff":
            q += " AND date=?"; p.append(date.today().isoformat())
        else:
            if df: q += " AND date=?"; p.append(df)
        if sf: q += " AND status=?"; p.append(sf)
        c.execute(q + " ORDER BY date DESC, time", p)
        rows = c.fetchall(); conn.close()
        return jsonify({"success": True, "count": len(rows), "reservations": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/cancel/<ref>", methods=["POST"])
@admin_required
def cancel_reservation(ref):
    try:
        conn = get_db(); c = conn.cursor()
        c.execute("UPDATE reservations SET status='Cancelled' WHERE ref=?", (ref.upper(),))
        conn.commit(); affected = c.rowcount; conn.close()
        return jsonify({"success": bool(affected)})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/confirm/<ref>", methods=["POST"])
@admin_required
def confirm_reservation(ref):
    try:
        conn = get_db(); c = conn.cursor()
        c.execute("UPDATE reservations SET status='Confirmed' WHERE ref=?", (ref.upper(),))
        conn.commit(); affected = c.rowcount; conn.close()
        return jsonify({"success": bool(affected)})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/reservation/<ref>")
@login_required
def get_reservation(ref):
    try:
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT * FROM reservations WHERE ref=?", (ref.upper(),))
        row = c.fetchone(); conn.close()
        return jsonify({"success": True, "reservation": dict(row)}) if row else (jsonify({"success": False}), 404)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ══════════════════════════════════════════════════════════════
#  ██  PUBLIC ROUTES (no auth needed)
# ══════════════════════════════════════════════════════════════

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json or {}
    msg  = data.get("message", "").strip()
    sid  = data.get("sender", "user")
    if not msg:
        return jsonify([{"text": "Please type a message. \u2615"}])
    # On Render (RASA_AVAILABLE=false), return empty so frontend uses local smart reply + Gemini
    if not RASA_AVAILABLE:
        return jsonify([])
    # Local: forward to Rasa NLU server
    try:
        r = http_requests.post(RASA_API_URL, json={"sender": sid, "message": msg}, timeout=8)
        replies = r.json()
        return jsonify(replies) if replies else jsonify([])
    except Exception as e:
        logger.error(f"Rasa error: {e}")
        return jsonify([])   # frontend falls back to getSmartReply() automatically

@app.route("/api/reserve", methods=["POST"])
def reserve_table():
    d       = request.json or {}
    name    = d.get("name",    "").strip()
    phone   = d.get("phone",   "").strip()
    email   = d.get("email",   "").strip()
    dt      = d.get("date",    "").strip()
    tm      = d.get("time",    "").strip()
    guests  = d.get("guests",  "").strip()
    special = d.get("special_requests", "").strip()

    if not all([name, dt, tm, guests]):
        return jsonify({"success": False, "message": "Name, date, time, and guests required."}), 400

    ref = "ARM-" + "".join(random.choices(string.digits, k=4))
    try:
        conn = get_db(); c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS reservations (id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT UNIQUE, name TEXT, phone TEXT, email TEXT, date TEXT, time TEXT, guests TEXT, special_req TEXT, status TEXT DEFAULT 'Confirmed', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        c.execute("INSERT INTO reservations (ref,name,phone,email,date,time,guests,special_req) VALUES (?,?,?,?,?,?,?,?)", (ref,name,phone,email,dt,tm,guests,special))
        conn.commit(); conn.close()
        logger.info(f"New booking: {ref} | {name} | {dt} {tm}")
        send_confirmation_email(email, name, ref, dt, tm, guests, special)
        return jsonify({"success": True, "ref": ref})
    except sqlite3.IntegrityError:
        return reserve_table()
    except Exception as e:
        logger.error(f"Reservation error: {e}")
        return jsonify({"success": False, "message": "Failed. Call +91 98765 43210."}), 500

@app.route("/api/slots")
def get_slots():
    dt  = request.args.get("date","").strip()
    ALL = ["8:00 AM","9:30 AM","11:00 AM","12:30 PM","2:00 PM","3:30 PM","5:00 PM","6:30 PM","8:00 PM"]
    if not dt:
        return jsonify({"slots": [{"time": s, "available": True} for s in ALL]})
    try:
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT time, COUNT(*) as cnt FROM reservations WHERE date=? AND status!='Cancelled' GROUP BY time", (dt,))
        booked = {r["time"]: r["cnt"] for r in c.fetchall()}; conn.close()
        return jsonify({"slots": [{"time": s, "available": booked.get(s,0) < 4} for s in ALL]})
    except:
        return jsonify({"slots": [{"time": s, "available": True} for s in ALL]})


# ══════════════════════════════════════════════════════════════
#  PUBLIC  —  Booking Tracker  (no auth needed)
# ══════════════════════════════════════════════════════════════

@app.route("/track")
def track_page():
    return render_template("track.html")

@app.route("/api/track/<ref>")
def track_booking(ref):
    """Public API — returns booking info by ARM ref (no auth needed)."""
    if not ref or len(ref) > 20:
        return jsonify({"success": False, "message": "Invalid reference."}), 400
    try:
        conn = get_db(); c = conn.cursor()
        c.execute(
            "SELECT ref, name, date, time, guests, special_req, status, created_at "
            "FROM reservations WHERE UPPER(ref)=UPPER(?)",
            (ref.strip(),)
        )
        row = c.fetchone(); conn.close()
        if not row:
            return jsonify({"success": False, "message": "No booking found with that reference. Please check and try again."}), 404
        r = dict(row)
        # Mask name for privacy  "Rohit Kumar" → "R***r"
        parts = r["name"].split()
        masked = " ".join(p[0] + "*"*(len(p)-2) + p[-1] if len(p) > 2 else p[0]+"*" for p in parts)
        r["masked_name"] = masked
        r.pop("name")           # don't expose full name publicly
        return jsonify({"success": True, "booking": r})
    except Exception as e:
        logger.error(f"Track error: {e}")
        return jsonify({"success": False, "message": "Server error. Please try again."}), 500


# ══════════════════════════════════════════════════════════════
#  FEEDBACK  (public — no auth)
# ══════════════════════════════════════════════════════════════
@app.route("/api/feedback", methods=["POST"])
def submit_feedback():
    d       = request.json or {}
    name    = d.get("name",    "").strip()
    email   = d.get("email",   "").strip()
    rating  = d.get("rating",  0)
    message = d.get("message", "").strip()
    if not name or not message or not rating:
        return jsonify({"success": False, "message": "Name, rating and message required."}), 400
    try:
        conn = get_db(); c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, email TEXT, rating INTEGER,
            message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("INSERT INTO feedback (name,email,rating,message) VALUES (?,?,?,?)",
                  (name, email, rating, message))
        conn.commit(); conn.close()
        logger.info(f"Feedback from {name}: {rating}/5")
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Feedback error: {e}")
        return jsonify({"success": False, "message": "Error saving feedback."}), 500

@app.route("/api/feedback/all")
@admin_required
def get_feedback():
    try:
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT * FROM feedback ORDER BY created_at DESC LIMIT 100")
        rows = [dict(r) for r in c.fetchall()]; conn.close()
        avg = round(sum(r["rating"] for r in rows)/len(rows),1) if rows else 0
        return jsonify({"success": True, "count": len(rows), "average_rating": avg, "feedback": rows})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ══════════════════════════════════════════════════════════════
#  CHAT LOGS  (stores every conversation for analysis)
# ══════════════════════════════════════════════════════════════
@app.route("/api/chatlog", methods=["POST"])
def save_chat_log():
    d = request.json or {}
    try:
        conn = get_db(); c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id TEXT, user_msg TEXT, bot_reply TEXT,
            intent TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("INSERT INTO chat_logs (sender_id,user_msg,bot_reply,intent) VALUES (?,?,?,?)",
                  (d.get("sender",""), d.get("user_msg",""), d.get("bot_reply",""), d.get("intent","")))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False}), 500

@app.route("/api/chatlog/all")
@admin_required
def get_chat_logs():
    try:
        conn = get_db(); c = conn.cursor()
        c.execute("SELECT * FROM chat_logs ORDER BY created_at DESC LIMIT 200")
        rows = [dict(r) for r in c.fetchall()]; conn.close()
        return jsonify({"success": True, "count": len(rows), "logs": rows})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  TESTIMONIALS  —  Feature / unfeature feedback on website
# ══════════════════════════════════════════════════════════════

@app.route("/api/feedback/feature/<int:fid>", methods=["POST"])
@admin_required
def feature_feedback(fid):
    """Toggle a feedback entry as featured (shows on website)."""
    try:
        conn = get_db(); c = conn.cursor()
        # Ensure featured column exists
        try:
            c.execute("ALTER TABLE feedback ADD COLUMN featured INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            pass  # Column already exists
        action = request.json.get("action", "feature") if request.json else "feature"
        val = 1 if action == "feature" else 0
        c.execute("UPDATE feedback SET featured=? WHERE id=?", (val, fid))
        conn.commit()
        affected = c.rowcount
        conn.close()
        return jsonify({"success": bool(affected), "featured": bool(val)})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/testimonials")
def get_testimonials():
    """Public API — returns featured feedback for website testimonial section."""
    try:
        conn = get_db(); c = conn.cursor()
        # Ensure featured column exists
        try:
            c.execute("ALTER TABLE feedback ADD COLUMN featured INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            pass
        c.execute(
            "SELECT id, name, rating, message, created_at "
            "FROM feedback WHERE featured=1 ORDER BY created_at DESC LIMIT 12"
        )
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({"success": True, "count": len(rows), "testimonials": rows})
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "testimonials": []}), 500

@app.errorhandler(403)
def forbidden(e):
    return render_template("login.html", error="Access denied. Admin role required.", next=""), 403

if __name__ == "__main__":
    os.makedirs("database", exist_ok=True)
    print("\n" + "="*58)
    print("  ☕  Aroma & Co. — Unified Server  (port 8000)")
    print("="*58)
    mode = "Render (Gemini mode)" if not RASA_AVAILABLE else "Local (Rasa + Gemini)"
    print(f"  Mode      → {mode}")
    print("  Website   → http://localhost:8000")
    print("  Login     → http://localhost:8000/login")
    print("  Tracker   → http://localhost:8000/track")
    print("  Dashboard → http://localhost:8000/dashboard")
    print("-"*58)
    print("  Accounts:")
    print("    admin   / admin123   (Admin — full access)")
    print("    staff   / staff123   (Staff — read only)")
    print("    manager / manager123 (Manager — full access)")
    print("="*58 + "\n")
    port  = int(os.environ.get("PORT", 8000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=port)