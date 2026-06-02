from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import sqlite3
import html
import bcrypt
import uuid
import time
import os

# =========================
# SECURITY CONFIG
# =========================

SESSIONS = {}  # session_id -> {user, expiry}
LOGIN_FAILS = {}  # ip -> [count, last_time]

SESSION_TIMEOUT = 1800  # 30 min
MAX_ATTEMPTS = 5
BLOCK_TIME = 60

# =========================
# DB
# =========================

def get_db():
    con = sqlite3.connect("data/cryptoportal.db")
    con.row_factory = sqlite3.Row
    return con


# =========================
# HELPERS
# =========================

def now():
    return time.time()


def clean_int(v):
    try:
        return int(v)
    except:
        return 0


def get_client_ip(handler):
    return handler.client_address[0]


def get_user(handler):
    cookie = handler.headers.get("Cookie", "")
    cookies = {}

    for part in cookie.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            cookies[k] = v

    sid = cookies.get("session")
    if not sid or sid not in SESSIONS:
        return None

    session = SESSIONS[sid]

    if session["expiry"] < now():
        del SESSIONS[sid]
        return None

    session["expiry"] = now() + SESSION_TIMEOUT
    return session["user"]


def block_ip(ip):
    data = LOGIN_FAILS.get(ip)

    if not data:
        return False

    count, last = data

    if count >= MAX_ATTEMPTS and now() - last < BLOCK_TIME:
        return True

    if now() - last > BLOCK_TIME:
        LOGIN_FAILS[ip] = [0, now()]

    return False


def fail_ip(ip):
    count, _ = LOGIN_FAILS.get(ip, [0, now()])
    LOGIN_FAILS[ip] = [count + 1, now()]


# =========================
# SERVER
# =========================

class Handler(BaseHTTPRequestHandler):

    # -------------------------
    # GET
    # -------------------------
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)

        user = get_user(self)

        # ---------------- CSS STATIC ----------------
        if path == "/style.css":
            if os.path.exists("www/style.css"):
                self.send_response(200)
                self.send_header("Content-type", "text/css")
                self.end_headers()
                self.wfile.write(open("www/style.css", "rb").read())
                return

        # ---------------- HOME ----------------
        if path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            page = open("www/main.html", "r", encoding="utf-8").read()
            page = page.replace("__LOGGED__", "yes" if user else "no")

            self.wfile.write(page.encode())
            return

        # ---------------- LOGIN ----------------
        if path == "/login":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(open("www/login.html", "rb").read())
            return

        # ---------------- REGISTER ----------------
        if path == "/register":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(open("www/register.html", "rb").read())
            return

        # ---------------- LOGOUT ----------------
        if path == "/logout":
            cookie = self.headers.get("Cookie", "")
            if "session=" in cookie:
                sid = cookie.split("session=")[-1].split(";")[0]
                SESSIONS.pop(sid, None)

            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
            return

        # ---------------- ORDERS (PROTECTED) ----------------
        if path == "/orderview":
            if not user:
                self.redirect("/login")
                return

            walletid = clean_int(params.get("walletid", ["0"])[0])

            con = get_db()
            cur = con.cursor()

            rows = cur.execute("""
                SELECT orderbook.id, crypto.name, side, price, currency, qty, status
                FROM orderbook
                JOIN crypto ON crypto.id = orderbook.cryptoid
                WHERE walletid = ?
            """, (walletid,)).fetchall()

            con.close()

            table = "<table border='1'><tr><th>ID</th><th>Crypto</th><th>Side</th><th>Price</th><th>Currency</th><th>Qty</th><th>Status</th></tr>"

            for r in rows:
                table += "<tr>" + "".join(f"<td>{html.escape(str(x))}</td>" for x in r) + "</tr>"

            table += "</table>"

            page = open("www/orderview.html", "r", encoding="utf-8").read()
            page = page.replace("__ORDERS__", table)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(page.encode())
            return

        # ---------------- ORDER PAGE ----------------
        if path == "/orderenter":
            if not user:
                self.redirect("/login")
                return

            con = get_db()
            cur = con.cursor()

            cryptos = cur.execute("SELECT id, name FROM crypto").fetchall()
            con.close()

            options = "".join(
                f"<option value='{c['id']}'>{html.escape(c['name'])}</option>"
                for c in cryptos
            )

            page = open("www/orderenter.html", "r", encoding="utf-8").read()
            page = page.replace("__CRYPTOS__", options)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(page.encode())
            return

        # ---------------- 404 ----------------
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not found")


    # -------------------------
    # POST
    # -------------------------
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        data = urllib.parse.parse_qs(self.rfile.read(length).decode())

        ip = get_client_ip(self)

        # =========================
        # REGISTER (SECURE)
        # =========================
        if path == "/register":
            username = data.get("username", [""])[0].strip()
            password = data.get("password", [""])[0].strip()

            if not username or not password:
                self.send_error(400)
                return

            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

            con = get_db()
            cur = con.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT UNIQUE,
                    password TEXT
                )
            """)

            try:
                cur.execute(
                    "INSERT INTO users VALUES (?, ?)",
                    (username, hashed)
                )
                con.commit()
            except:
                self.send_error(409)
                return

            con.close()

            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        # =========================
        # LOGIN (BRUTE FORCE PROTECTED)
        # =========================
        if path == "/login":

            if block_ip(ip):
                self.send_error(429)
                return

            username = data.get("username", [""])[0]
            password = data.get("password", [""])[0]

            con = get_db()
            cur = con.cursor()

            user = cur.execute(
                "SELECT password FROM users WHERE username=?",
                (username,)
            ).fetchone()

            con.close()

            if user and bcrypt.checkpw(password.encode(), user[0].encode()):
                sid = str(uuid.uuid4())

                SESSIONS[sid] = {
                    "user": username,
                    "expiry": now() + SESSION_TIMEOUT
                }

                self.send_response(302)
                self.send_header("Location", "/")
                self.send_header("Set-Cookie", f"session={sid}; HttpOnly; SameSite=Strict")
                self.end_headers()
                return

            fail_ip(ip)
            self.send_error(401)
            return

        # =========================
        # ORDER ENTER (PROTECTED)
        # =========================
        if path == "/orderenter":
            user = get_user(self)
            if not user:
                self.send_error(403)
                return

            walletid = clean_int(data.get("walletid", ["0"])[0])
            cryptoid = clean_int(data.get("cryptoid", ["1"])[0])
            side = data.get("side", ["Buy"])[0]
            price = clean_int(data.get("price", ["0"])[0])
            currency = data.get("currency", ["EUR"])[0]
            qty = clean_int(data.get("quantity", ["0"])[0])

            con = get_db()
            cur = con.cursor()

            oid = cur.execute("SELECT COALESCE(MAX(id),0)+1 FROM orderbook").fetchone()[0]

            cur.execute("""
                INSERT INTO orderbook VALUES (?, ?, ?, ?, ?, ?, ?, 'NEW')
            """, (oid, walletid, cryptoid, side, price, currency, qty))

            con.commit()
            con.close()

            self.send_response(303)
            self.send_header("Location", f"/orderview?walletid={walletid}")
            self.end_headers()

    # -------------------------
    def redirect(self, url):
        self.send_response(302)
        self.send_header("Location", url)
        self.end_headers()


# =========================
# START SERVER
# =========================

httpd = HTTPServer(("", 8080), Handler)
print("Secure CryptoPortal running on http://localhost:8080")

try:
    httpd.serve_forever()
except KeyboardInterrupt:
    httpd.server_close()