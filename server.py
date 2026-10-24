"""MH Spices server (Python only, nothing to install).

Serves the shop at http://localhost:8000 and provides:
  - customer accounts (register / log in) and an admin login
  - order storage in a local SQLite database (shop.db)
  - the order email with a PDF attached (sent through Gmail)

Create the admin account once:
    python server.py create-admin

Start the server (see start-server.ps1 for the Gmail email setting):
    python server.py

Set DRY_RUN=1 to save the order PDF in the "out" folder instead of emailing it.
"""
import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import sqlite3
import sys
import time
from datetime import datetime
from email.message import EmailMessage
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DB_PATH") or HERE / "shop.db")
OWNER_EMAIL = "aminamh2920@gmail.com"   # gets a copy of every order
SHOP_NAME = "MH Spices"
PDF_CURRENCY = "Rs."                    # the PDF's built-in font has no rupee sign
PORT = int(os.environ.get("PORT", "8000"))
SECURE_COOKIES = bool(os.environ.get("SECURE_COOKIES"))   # set to 1 when the site runs on https
BLOCKED_SUFFIXES = (".py", ".php", ".db", ".ps1")         # never serve source or data files
SESSION_DAYS = 14
ORDER_STATUSES = ("New", "Confirmed", "Packed", "Delivered", "Cancelled")


# ── Database ───────────────────────────────────────────────────────
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            first_name TEXT NOT NULL, last_name TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '', location TEXT NOT NULL DEFAULT '',
            pw_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions(
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY,
            order_code TEXT NOT NULL UNIQUE,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            customer TEXT NOT NULL, items TEXT NOT NULL,
            total REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'New',
            emailed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS product_overrides(
            id INTEGER PRIMARY KEY, price REAL NOT NULL, in_stock INTEGER NOT NULL
        );
        """)


# ── Passwords and sessions ─────────────────────────────────────────
def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${h.hex()}"


def check_password(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split("$")
        calc = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(calc.hex(), h)
    except (ValueError, TypeError):
        return False


DUMMY_HASH = hash_password("not-a-real-password")   # so a wrong email takes as long as a wrong password


def new_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with db() as c:
        c.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))
        c.execute("INSERT INTO sessions VALUES(?,?,?)",
                  (hashlib.sha256(token.encode()).hexdigest(), user_id, time.time() + SESSION_DAYS * 86400))
    return token


def user_public(r: sqlite3.Row) -> dict:
    return {"id": r["id"], "firstName": r["first_name"], "lastName": r["last_name"], "email": r["email"],
            "phone": r["phone"], "address": r["address"], "location": r["location"], "role": r["role"]}


# simple in-memory limiter: stops people guessing passwords
_attempts: dict[str, list[float]] = {}


def too_many(key: str, limit: int, window: int) -> bool:
    now = time.time()
    hits = [t for t in _attempts.get(key, []) if now - t < window]
    _attempts[key] = hits
    return len(hits) >= limit


def note_attempt(key: str) -> None:
    _attempts.setdefault(key, []).append(time.time())


# ── Products (names come from js/products.js, price and stock can be edited by the admin) ──
def base_products() -> list[dict]:
    out = []
    for line in (HERE / "js" / "products.js").read_text(encoding="utf-8").splitlines():
        if not re.match(r"\s*\{\s*id:", line):
            continue
        try:
            out.append({
                "id": int(re.search(r"id:\s*(\d+)", line).group(1)),
                "name": re.search(r'name:\s*"([^"]+)"', line).group(1),
                "unit": re.search(r'unit:\s*"([^"]+)"', line).group(1),
                "price": float(re.search(r"price:\s*([\d.]+)", line).group(1)),
                "inStock": re.search(r"inStock:\s*(true|false)", line).group(1) == "true",
            })
        except AttributeError:
            continue
    return out


def get_products() -> list[dict]:
    with db() as c:
        ov = {r["id"]: r for r in c.execute("SELECT * FROM product_overrides")}
    prods = base_products()
    for p in prods:
        if p["id"] in ov:
            p["price"], p["inStock"] = ov[p["id"]]["price"], bool(ov[p["id"]]["in_stock"])
    return prods


# ── PDF (plain text document, Helvetica, no libraries) ─────────────
def pdf_str(s: str) -> bytes:
    for a, b in {"•": "-", "–": "-", "—": "-", "’": "'", "‘": "'", "“": '"', "”": '"'}.items():
        s = s.replace(a, b)
    raw = s.encode("cp1252", errors="replace")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def pdf_build(pages: list[bytes]) -> bytes:
    objs: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: ("<< /Type /Pages /Kids [%s] /Count %d >>" % (" ".join(f"{5 + i * 2} 0 R" for i in range(len(pages))), len(pages))).encode(),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    }
    for i, content in enumerate(pages):
        pg = 5 + i * 2
        objs[pg] = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {pg + 1} 0 R >>").encode()
        objs[pg + 1] = b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream"
    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for num, body in objs.items():
        offsets[num] = len(out)
        out += b"%d 0 obj\n" % num + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for num in sorted(offsets):
        out += b"%010d 00000 n \n" % offsets[num]
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref)
    return bytes(out)


def wrap(text: str, width: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + ([cur] if cur else [])


def order_pdf(order_id: str, c: dict, items: list[dict], total: float) -> bytes:
    pages: list[bytes] = []
    cur = bytearray()
    y = 790

    def put(x, text, size=11, bold=False):
        cur.extend(b"BT /%s %d Tf %d %d Td (" % (b"F2" if bold else b"F1", size, x, y) + pdf_str(text) + b") Tj ET\n")

    def new_page():
        nonlocal cur, y
        pages.append(bytes(cur))
        cur = bytearray()
        y = 790

    def rule():
        cur.extend(b"50 %d m 545 %d l S\n" % (y, y))

    put(50, SHOP_NAME, 22, True); y -= 22
    put(50, "Order confirmation", 13); y -= 34
    put(50, f"Order no: {order_id}", 11, True); y -= 16
    put(50, "Date: " + datetime.now().strftime("%d %b %Y, %H:%M"), 11); y -= 28
    put(50, "Customer", 11, True); y -= 16
    for line in (c["name"], c["phone"], c["email"]):
        put(50, line, 11); y -= 15
    for line in wrap(f'{c["address"]}, {c["location"]}', 80):
        put(50, line, 11); y -= 15
    y -= 18
    put(50, "Item", 11, True); put(320, "Qty", 11, True); put(380, "Price", 11, True); put(470, "Amount", 11, True)
    y -= 8; rule(); y -= 16
    for it in items:
        if y < 90:
            new_page()
        put(50, f'{it["name"]} ({it["unit"]})'); put(320, str(it["qty"]))
        put(380, f'{PDF_CURRENCY} {it["price"]:,.0f}'); put(470, f'{PDF_CURRENCY} {it["price"] * it["qty"]:,.0f}')
        y -= 18
    if y < 120:
        new_page()
    rule(); y -= 22
    put(380, "Total", 12, True); put(470, f"{PDF_CURRENCY} {total:,.0f}", 12, True); y -= 40
    put(50, "Thank you for your order. We will confirm the final price and delivery with you on WhatsApp.", 10)
    pages.append(bytes(cur))
    return pdf_build(pages)


# ── Orders and email ───────────────────────────────────────────────
def clean(v, limit: int) -> str:
    return re.sub(r"[\x00-\x1f\x7f]+", " ", str(v or "")).strip()[:limit]


EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def parse_order(d: dict):
    """Return (order_id, customer, items, total) or an error message string."""
    if not isinstance(d, dict):
        return "Invalid order."
    order_id = re.sub(r"[^A-Z0-9]", "", str(d.get("orderId", "")).upper())
    cust = d.get("customer") if isinstance(d.get("customer"), dict) else {}
    c = {k: clean(cust.get(k), n) for k, n in
         [("firstName", 40), ("lastName", 40), ("phone", 25), ("email", 120), ("address", 300), ("location", 160)]}
    c["name"] = f'{c["firstName"]} {c["lastName"]}'.strip()
    if not order_id or len(order_id) > 20 or not all(c[k] for k in ("firstName", "lastName", "phone", "address", "location")):
        return "Please fill in all your details."
    if not EMAIL_RE.fullmatch(c["email"]):
        return "Please enter a valid email address."
    catalog = {p["id"]: p for p in get_products()}
    items, total = [], 0.0
    for it in (d.get("items") if isinstance(d.get("items"), list) else [])[:40]:
        try:
            pid, qty = int(it.get("id")), int(it.get("qty", 0))
        except (TypeError, ValueError, AttributeError):
            continue
        p = catalog.get(pid)
        if not p or not 1 <= qty <= 100:
            continue
        if not p["inStock"]:
            return f'{p["name"]} is out of stock.'
        items.append({"id": pid, "name": p["name"], "unit": p["unit"], "qty": qty, "price": p["price"]})   # price from the server, not the browser
        total += qty * p["price"]
    return (order_id, c, items, total) if items else "Your cart is empty."


def send_email(order_id: str, c: dict, items: list, total: float) -> bool:
    pdf = order_pdf(order_id, c, items, total)
    if os.environ.get("DRY_RUN"):
        out = HERE / "out"
        out.mkdir(exist_ok=True)
        (out / f"order-{order_id}.pdf").write_bytes(pdf)
        print(f"DRY_RUN: saved out/order-{order_id}.pdf")
        return True

    user, password = os.environ.get("GMAIL_USER"), os.environ.get("GMAIL_APP_PASSWORD")
    if not user or not password:
        print("GMAIL_USER / GMAIL_APP_PASSWORD are not set, so no email was sent.")
        return False

    msg = EmailMessage()
    msg["Subject"] = f"Your {SHOP_NAME} order {order_id}"
    msg["From"] = f"{SHOP_NAME} <{user}>"
    msg["To"] = c["email"]
    msg["Bcc"] = OWNER_EMAIL
    msg.set_content(
        f'Hello {c["name"]},\n\nThank you for your order {order_id} with {SHOP_NAME}.\n'
        "Your order summary is attached as a PDF.\n\n"
        f"We will confirm the final price and delivery with you on WhatsApp.\n\n{SHOP_NAME}"
    )
    msg.add_attachment(pdf, maintype="application", subtype="pdf", filename=f"order-{order_id}.pdf")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as s:
            s.login(user, password.replace(" ", ""))
            s.send_message(msg)
        return True
    except Exception as e:  # smtplib raises many kinds of errors; report and carry on
        print("Email failed:", e)
        return False


# ── HTTP ───────────────────────────────────────────────────────────
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(HERE), **kw)

    # helpers
    def reply(self, code: int, body: dict, cookie: str | None = None):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def err(self, code: int, msg: str):
        self.reply(code, {"ok": False, "error": msg})

    def cookie(self, token: str, max_age: int) -> str:
        c = f"mh_session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age={max_age}"
        return c + ("; Secure" if SECURE_COOKIES else "")

    def user(self):
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        try:
            token = SimpleCookie(raw)["mh_session"].value
        except (KeyError, Exception):
            return None
        th = hashlib.sha256(token.encode()).hexdigest()
        with db() as c:
            return c.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?",
                             (th, time.time())).fetchone()

    def json_body(self):
        # JSON only: a web page on another site cannot send this without our permission (CSRF protection)
        if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
            return None
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 20000:
                return None
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def ip(self) -> str:
        return self.client_address[0]

    # routing
    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/api/"):
            return self.api_get(path)
        if path.lower().endswith(BLOCKED_SUFFIXES) or "/." in path or path.startswith("/out"):
            return self.send_error(404)
        super().do_GET()

    def end_headers(self):
        if self.command == "GET" and not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache")   # always show the newest files while editing
        super().end_headers()

    def do_POST(self):
        path = self.path.split("?")[0]
        data = self.json_body()
        if data is None:
            return self.err(400, "Invalid request.")
        routes = {
            "/api/register": self.register, "/api/login": self.login, "/api/logout": self.logout,
            "/sendmail.php": self.place_order,
            "/api/admin/order-status": self.admin_order_status, "/api/admin/product": self.admin_product,
        }
        fn = routes.get(path)
        return fn(data) if fn else self.err(404, "Not found.")

    # public API
    def api_get(self, path: str):
        u = self.user()
        if path == "/api/me":
            return self.reply(200, {"user": user_public(u) if u else None})
        if path == "/api/products":
            return self.reply(200, {"products": get_products()})
        if path == "/api/my-orders":
            if not u:
                return self.err(401, "Please log in.")
            with db() as c:
                rows = c.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 50", (u["id"],)).fetchall()
            return self.reply(200, {"orders": [self.order_dict(r) for r in rows]})
        if path.startswith("/api/admin/"):
            if not u or u["role"] != "admin":
                return self.err(403, "Admin access only.")
            return self.admin_get(path)
        return self.err(404, "Not found.")

    @staticmethod
    def order_dict(r: sqlite3.Row) -> dict:
        return {"id": r["id"], "code": r["order_code"], "customer": json.loads(r["customer"]), "items": json.loads(r["items"]),
                "total": r["total"], "status": r["status"], "emailed": bool(r["emailed"]), "createdAt": r["created_at"]}

    def register(self, d: dict):
        if too_many("reg:" + self.ip(), 10, 3600):
            return self.err(429, "Too many attempts. Please try again later.")
        note_attempt("reg:" + self.ip())
        f = {k: clean(d.get(k), n) for k, n in [("firstName", 40), ("lastName", 40), ("email", 120), ("phone", 25), ("address", 300), ("location", 160)]}
        pw = str(d.get("password") or "")
        if not f["firstName"] or not f["lastName"]:
            return self.err(400, "Please enter your first and last name.")
        if not EMAIL_RE.fullmatch(f["email"]):
            return self.err(400, "Please enter a valid email address.")
        if not 8 <= len(pw) <= 128:
            return self.err(400, "Password must be at least 8 characters.")
        try:
            with db() as c:
                cur = c.execute("INSERT INTO users(email,first_name,last_name,phone,address,location,pw_hash,role,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                                (f["email"], f["firstName"], f["lastName"], f["phone"], f["address"], f["location"],
                                 hash_password(pw), "customer", datetime.now().isoformat(timespec="seconds")))
                uid = cur.lastrowid
        except sqlite3.IntegrityError:
            return self.err(409, "An account with this email already exists. Please log in.")
        with db() as c:
            row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        self.reply(200, {"ok": True, "user": user_public(row)}, self.cookie(new_session(uid), SESSION_DAYS * 86400))

    def login(self, d: dict):
        email, pw = clean(d.get("email"), 120), str(d.get("password") or "")[:128]
        key = f"login:{self.ip()}:{email.lower()}"
        if too_many(key, 8, 600):
            return self.err(429, "Too many attempts. Please wait a few minutes and try again.")
        with db() as c:
            row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        ok = check_password(pw, row["pw_hash"] if row else DUMMY_HASH)
        if not (row and ok):
            note_attempt(key)
            return self.err(401, "Incorrect email or password.")
        self.reply(200, {"ok": True, "user": user_public(row)}, self.cookie(new_session(row["id"]), SESSION_DAYS * 86400))

    def logout(self, d: dict):
        raw = self.headers.get("Cookie")
        try:
            token = SimpleCookie(raw)["mh_session"].value if raw else None
        except Exception:
            token = None
        if token:
            with db() as c:
                c.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
        self.reply(200, {"ok": True}, self.cookie("", 0))

    def place_order(self, d: dict):
        if d.get("website"):                       # honeypot: bots fill this in
            return self.reply(200, {"ok": True})
        if too_many("order:" + self.ip(), 20, 3600):
            return self.err(429, "Too many orders. Please try again later.")
        note_attempt("order:" + self.ip())
        parsed = parse_order(d)
        if isinstance(parsed, str):
            return self.err(400, parsed)
        order_id, c, items, total = parsed
        u = self.user()
        try:
            with db() as conn:
                conn.execute("INSERT INTO orders(order_code,user_id,customer,items,total,created_at) VALUES(?,?,?,?,?,?)",
                             (order_id, u["id"] if u else None, json.dumps(c), json.dumps(items), total,
                              datetime.now().isoformat(timespec="seconds")))
                if u:   # remember the delivery details on the customer's account
                    conn.execute("UPDATE users SET phone=?, address=?, location=? WHERE id=?", (c["phone"], c["address"], c["location"], u["id"]))
        except sqlite3.IntegrityError:
            return self.err(409, "This order was already placed.")
        emailed = send_email(order_id, c, items, total)
        if emailed:
            with db() as conn:
                conn.execute("UPDATE orders SET emailed=1 WHERE order_code=?", (order_id,))
        self.reply(200, {"ok": emailed, "saved": True})

    # admin API
    def admin_get(self, path: str):
        with db() as c:
            if path == "/api/admin/orders":
                rows = c.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 500").fetchall()
                return self.reply(200, {"orders": [self.order_dict(r) for r in rows], "statuses": ORDER_STATUSES})
            if path == "/api/admin/customers":
                rows = c.execute("""SELECT u.*, (SELECT COUNT(*) FROM orders o WHERE o.user_id=u.id) AS n
                                    FROM users u ORDER BY u.id DESC""").fetchall()
                return self.reply(200, {"customers": [{**user_public(r), "orders": r["n"], "createdAt": r["created_at"]} for r in rows]})
        if path == "/api/admin/products":
            return self.reply(200, {"products": get_products()})
        return self.err(404, "Not found.")

    def require_admin(self):
        u = self.user()
        if not u or u["role"] != "admin":
            self.err(403, "Admin access only.")
            return None
        return u

    def admin_order_status(self, d: dict):
        if not self.require_admin():
            return
        status = d.get("status")
        if status not in ORDER_STATUSES:
            return self.err(400, "Invalid status.")
        try:
            oid = int(d.get("id"))
        except (TypeError, ValueError):
            return self.err(400, "Invalid order.")
        with db() as c:
            c.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
        self.reply(200, {"ok": True})

    def admin_product(self, d: dict):
        if not self.require_admin():
            return
        try:
            pid, price = int(d.get("id")), float(d.get("price"))
        except (TypeError, ValueError):
            return self.err(400, "Invalid product or price.")
        if pid not in {p["id"] for p in base_products()} or not 0 <= price <= 100000:
            return self.err(400, "Invalid product or price.")
        with db() as c:
            c.execute("INSERT INTO product_overrides VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET price=excluded.price, in_stock=excluded.in_stock",
                      (pid, price, 1 if d.get("inStock") else 0))
        self.reply(200, {"ok": True})


# ── Command line ───────────────────────────────────────────────────
def create_admin() -> None:
    init_db()
    email = input("Admin email: ").strip()
    if not EMAIL_RE.fullmatch(email):
        sys.exit("That is not a valid email address.")
    first = input("First name: ").strip() or "Admin"
    last = input("Last name: ").strip() or "."
    pw = getpass.getpass("Password (at least 8 characters, hidden): ")
    if len(pw) < 8 or pw != getpass.getpass("Type it again: "):
        sys.exit("Passwords did not match or were too short. Nothing was saved.")
    with db() as c:
        c.execute("""INSERT INTO users(email,first_name,last_name,pw_hash,role,created_at) VALUES(?,?,?,?, 'admin', ?)
                     ON CONFLICT(email) DO UPDATE SET pw_hash=excluded.pw_hash, role='admin'""",
                  (email, first, last, hash_password(pw), datetime.now().isoformat(timespec="seconds")))
    print(f"Admin account ready: {email}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "create-admin":
        create_admin()
        sys.exit(0)
    init_db()
    print(f"MH Spices running at http://localhost:{PORT}  (Ctrl+C to stop)")
    if os.environ.get("DRY_RUN"):
        print("DRY_RUN is on: PDFs are saved in the 'out' folder, no email is sent.")
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)
