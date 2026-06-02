#! /usr/bin/python3

from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import sqlite3
import html
import hashlib
import uuid
import os

# -------------------------
# SESSION STORAGE (RAM)
# -------------------------
SESSIONS = {}

# -------------------------
# HELPERS
# -------------------------
def convert_int(s):
    try:
        return int(s)
    except ValueError:
        return 0


def get_db():
    return sqlite3.connect("data/cryptoportal.db")


def get_user_from_request(self):
    cookie = self.headers.get("Cookie", "")
    cookies = {}

    for part in cookie.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            cookies[k] = v

    session_id = cookies.get("session")
    return SESSIONS.get(session_id)


VALID_SIDES = {"Buy", "Sell"}
VALID_CURRENCIES = {"EUR", "USD", "GBP"}

# -------------------------
# SERVER
# -------------------------
class HTTPRequestHandler(BaseHTTPRequestHandler):

    # -------------------------
    # GET
    # -------------------------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        urlparams = urllib.parse.parse_qs(parsed.query)

        # -------------------------
        # STATIC FILES (CSS / JS / IMAGES / ETC)
        # -------------------------
        file_path = "www" + path
        if path != "/" and os.path.isfile(file_path):
            self.send_response(200)

            if file_path.endswith(".css"):
                self.send_header("Content-type", "text/css")
            elif file_path.endswith(".js"):
                self.send_header("Content-type", "application/javascript")
            elif file_path.endswith(".jpeg") or file_path.endswith(".jpg"):
                self.send_header("Content-type", "image/jpeg")
            else:
                self.send_header("Content-type", "application/octet-stream")

            self.end_headers()

            with open(file_path, "rb") as f:
                self.wfile.write(f.read())
            return

        # -------------------------
        # HOME
        # -------------------------
        if path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open("www/main.html", "rb") as f:
                self.wfile.write(f.read())
            return

        # -------------------------
        # LOGIN PAGE
        # -------------------------
        elif path == "/login":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open("www/login.html", "rb") as f:
                self.wfile.write(f.read())
            return

        # -------------------------
        # REGISTER PAGE
        # -------------------------
        elif path == "/register":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open("www/register.html", "rb") as f:
                self.wfile.write(f.read())
            return

        # -------------------------
        # LOGOUT
        # -------------------------
        elif path == "/logout":
            cookie = self.headers.get("Cookie", "")
            if "session=" in cookie:
                session_id = cookie.split("session=")[-1].split(";")[0]
                SESSIONS.pop(session_id, None)

            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        # -------------------------
        # ORDER VIEW (PROTECTED)
        # -------------------------
        elif path == "/orderview":
            user = get_user_from_request(self)
            if not user:
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return

            walletid = convert_int(urlparams.get("walletid", ["0"])[0])

            con = get_db()
            cur = con.cursor()

            orders = """
            <table border="1">
            <tr>
                <th>Wallet</th><th>Order</th><th>Crypto</th>
                <th>Side</th><th>Price</th><th>Currency</th>
                <th>Qty</th><th>Status</th>
            </tr>
            """

            for row in cur.execute("""
                SELECT orderbook.walletid, orderbook.id, crypto.name,
                       orderbook.side, orderbook.price,
                       orderbook.currency, orderbook.qty, orderbook.status
                FROM orderbook
                JOIN crypto ON crypto.id = orderbook.cryptoid
                WHERE orderbook.walletid = ?
            """, (walletid,)):

                orders += "<tr>" + "".join(
                    f"<td>{html.escape(str(x))}</td>" for x in row
                ) + "</tr>"

            orders += "</table>"

            cur.close()
            con.close()

            with open("www/orderview.html", "r", encoding="utf-8") as f:
                page = f.read()

            page = page.replace("__WALLETID__", str(walletid))
            page = page.replace("__ORDERS__", orders)

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(page.encode("utf-8"))
            return

        # -------------------------
        # ORDER ENTER PAGE (PROTECTED)
        # -------------------------
        elif path == "/orderenter":
            user = get_user_from_request(self)
            if not user:
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return

            con = get_db()
            cur = con.cursor()

            htmlcryptos = ""
            for row in cur.execute("SELECT id, name FROM crypto"):
                htmlcryptos += f"<option value='{row[0]}'>{html.escape(row[1])}</option>"

            cur.close()
            con.close()

            with open("www/orderenter.html", "r", encoding="utf-8") as f:
                page = f.read()

            page = page.replace("__CRYPTOS__", htmlcryptos)

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(page.encode("utf-8"))
            return

        # -------------------------
        # 404
        # -------------------------
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open("www/error404.html", "rb") as f:
                self.wfile.write(f.read())
            return

    # -------------------------
    # POST
    # -------------------------
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        data = urllib.parse.parse_qs(body)

        # -------------------------
        # REGISTER
        # -------------------------
        if path == "/register":
            username = data.get("username", [""])[0].strip()
            password = data.get("password", [""])[0].strip()

            if not username or not password:
                self.send_response(400)
                self.end_headers()
                return

            password_hash = hashlib.sha256(password.encode()).hexdigest()

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
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, password_hash)
                )
                con.commit()
            except sqlite3.IntegrityError:
                self.send_response(409)
                self.end_headers()
                return

            cur.close()
            con.close()

            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        # -------------------------
        # LOGIN
        # -------------------------
        elif path == "/login":
            username = data.get("username", [""])[0]
            password = data.get("password", [""])[0]
            password_hash = hashlib.sha256(password.encode()).hexdigest()

            con = get_db()
            cur = con.cursor()

            user = cur.execute(
                "SELECT password FROM users WHERE username=?",
                (username,)
            ).fetchone()

            cur.close()
            con.close()

            if user and user[0] == password_hash:
                session_id = str(uuid.uuid4())
                SESSIONS[session_id] = username

                self.send_response(302)
                self.send_header("Location", "/")
                self.send_header("Set-Cookie", f"session={session_id}; HttpOnly")
                self.end_headers()
            else:
                self.send_response(401)
                self.end_headers()
            return

        # -------------------------
        # ORDER ENTER
        # -------------------------
        elif path == "/orderenter":
            user = get_user_from_request(self)
            if not user:
                self.send_response(302)
                self.send_header("Location", "/login")
                self.end_headers()
                return

            walletid = convert_int(data.get("walletid", ["0"])[0])
            cryptoid = convert_int(data.get("cryptoid", ["1"])[0])
            side = data.get("side", ["Buy"])[0]
            price = convert_int(data.get("price", ["0"])[0])
            currency = data.get("currency", ["EUR"])[0]
            qty = convert_int(data.get("quantity", ["0"])[0])

            if walletid <= 0 or price <= 0 or qty <= 0:
                self.send_error(400)
                return

            if side not in VALID_SIDES or currency not in VALID_CURRENCIES:
                self.send_error(400)
                return

            con = get_db()
            cur = con.cursor()

            exists = cur.execute(
                "SELECT COUNT(*) FROM wallet WHERE id=?",
                (walletid,)
            ).fetchone()[0]

            if exists == 0:
                self.send_error(401)
                return

            orderid = cur.execute(
                "SELECT COALESCE(MAX(id), 0) FROM orderbook"
            ).fetchone()[0] + 1

            cur.execute("""
                INSERT INTO orderbook
                (id, walletid, cryptoid, side, price, currency, qty, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (orderid, walletid, cryptoid, side, price, currency, qty, "NEW"))

            con.commit()
            cur.close()
            con.close()

            self.send_response(303)
            self.send_header("Location", f"/orderview?walletid={walletid}")
            self.end_headers()
            return


# -------------------------
# START SERVER
# -------------------------
httpd = HTTPServer(("", 8080), HTTPRequestHandler)
print("CryptoPortal running on http://localhost:8080")

try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print("Stopping server...")
    httpd.server_close()