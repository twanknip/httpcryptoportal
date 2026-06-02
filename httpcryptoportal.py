#!/usr/bin/python3

from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import sqlite3
from html import escape as html_escape
import bcrypt
import uuid
import json
import logging
from datetime import datetime

# =====================================================
# CONFIGURATIE
# =====================================================

LOG_FILE = "data/cryptoportal.log"
DB_FILE = "data/cryptoportal.db"
HOST = "0.0.0.0"
PORT = 8080
SESSION_TIMEOUT = 3600  # 1 uur

# Logging instellen
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# =====================================================
# SESSIES
# =====================================================

SESSIONS = {}  # session_id -> {'walletid': id, 'timestamp': tijd}


# =====================================================
# DATABASE FUNCTIES
# =====================================================

def get_db():
    con = sqlite3.connect(DB_FILE)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def get_wallet_by_id(walletid):
    """Haalt portefeuille gegevens op"""
    con = get_db()
    cur = con.cursor()
    result = cur.execute(
        "SELECT id, eigenaar FROM wallet WHERE id = ?",
        (walletid,)
    ).fetchone()
    con.close()
    return result


def verify_pin(walletid, pin):
    """Verifieert PIN met bcrypt"""
    con = get_db()
    cur = con.cursor()
    result = cur.execute(
        "SELECT pincode FROM wallet WHERE id = ?",
        (walletid,)
    ).fetchone()
    con.close()

    if not result:
        return False

    try:
        return bcrypt.checkpw(pin.encode(), result[0].encode())
    except Exception as e:
        logging.error(f"PIN verificatie fout: {e}")
        return False


def get_crypto_list():
    """Haalt alle beschikbare cryptocurrencies op"""
    con = get_db()
    cur = con.cursor()
    result = cur.execute(
        "SELECT id, naam, symbool FROM crypto ORDER BY id"
    ).fetchall()
    con.close()
    return result


def get_wallet_orders(walletid):
    """Haalt alle orders voor een portefeuille op"""
    con = get_db()
    cur = con.cursor()
    result = cur.execute("""
        SELECT 
            o.id, 
            c.naam, 
            c.symbool,
            o.zijde, 
            o.prijs, 
            o.munteenheid, 
            o.hoeveelheid, 
            o.status,
            o.datum_aangemaakt
        FROM orderbook o
        JOIN crypto c ON o.cryptoid = c.id
        WHERE o.walletid = ?
        ORDER BY o.id DESC
    """, (walletid,)).fetchall()
    con.close()
    return result


def create_order(walletid, cryptoid, zijde, prijs, munteenheid, hoeveelheid):
    """Maakt een nieuwe order aan"""
    con = get_db()
    cur = con.cursor()
    try:
        cur.execute("""
            INSERT INTO orderbook 
            (walletid, cryptoid, zijde, prijs, munteenheid, hoeveelheid, status)
            VALUES (?, ?, ?, ?, ?, ?, 'NIEUW')
        """, (walletid, cryptoid, zijde, prijs, munteenheid, hoeveelheid))
        con.commit()
        logging.info(f"Order aangemaakt - Portefeuille: {walletid}, Crypto: {cryptoid}")
        return True
    except Exception as e:
        logging.error(f"Fout bij orderaanmaak: {e}")
        return False
    finally:
        con.close()


# =====================================================
# HELPER FUNCTIES
# =====================================================

def read_post_data(handler):
    """Leest POST data uit request"""
    try:
        length = int(handler.headers.get("Content-Length", 0))
        body = handler.rfile.read(length).decode()
        return urllib.parse.parse_qs(body)
    except Exception as e:
        logging.error(f"POST data lees fout: {e}")
        return {}


def get_session(handler):
    """Haalt session ID uit cookie"""
    cookie = handler.headers.get("Cookie", "")
    for part in cookie.split(";"):
        if "sessie=" in part:
            sid = part.split("=")[1].strip()
            if sid in SESSIONS:
                return SESSIONS[sid].get('walletid')
    return None


def send_html_response(handler, status_code, html_content):
    """Stuurt HTML response"""
    handler.send_response(status_code)
    handler.send_header("Content-type", "text/html; charset=utf-8")
    handler.end_headers()
    handler.wfile.write(html_content.encode("utf-8"))


def send_redirect(handler, location, session_id=None):
    """Stuurt redirect response"""
    handler.send_response(302)
    if session_id:
        handler.send_header("Set-Cookie", 
            f"sessie={session_id}; HttpOnly; SameSite=Strict; Path=/")
    handler.send_header("Location", location)
    handler.end_headers()


# =====================================================
# HTML TEMPLATES
# =====================================================

def get_page_header():
    """Geeft HTML header terug"""
    return """
    <!DOCTYPE html>
    <html lang="nl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CryptoPortal</title>
        <link rel="stylesheet" href="/style.css">
    </head>
    <body>
    <div class="container">
    """


def get_page_footer():
    """Geeft HTML footer terug"""
    return """
    </div>
    </body>
    </html>
    """


# =====================================================
# REQUEST HANDLER
# =====================================================

class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        """Onderdrukt standaard logging"""
        pass

    # ===== GET =====
    def do_GET(self):
        """Verwerkt GET requests"""
        path = urllib.parse.urlparse(self.path).path
        walletid = get_session(self)

        # --------- STATISCHE BESTANDEN ---------
        if path in ["/style.css", "/login.html", "/main.html", "/register.html"]:
            try:
                with open(f"www{path}", "rb") as f:
                    content = f.read()
                    mime_type = "text/css" if path.endswith(".css") else "text/html; charset=utf-8"
                    self.send_response(200)
                    self.send_header("Content-type", mime_type)
                    self.end_headers()
                    self.wfile.write(content)
                    return
            except FileNotFoundError:
                pass

        # --------- AFBEELDINGEN ---------
        if path in ["/cryptoportal.jpeg", "/cryptoportal_orig.jpeg"]:
            try:
                with open(f"www{path}", "rb") as f:
                    self.send_response(200)
                    self.send_header("Content-type", "image/jpeg")
                    self.end_headers()
                    self.wfile.write(f.read())
                    return
            except FileNotFoundError:
                pass

        # --------- HOME ---------
        if path == "/":
            html = get_page_header()
            html += """
            <div class="header">
                <h1>CryptoPortal</h1>
                <p class="subtitle">Veilig crypto handelen</p>
            </div>

            <div class="welcome-box">
                <h2>Welkom</h2>
                <p>Beheer en handel je cryptocurrency portefeuille veilig en snel.</p>
            </div>

            <div class="nav-links">
                <a href="/orders" class="btn btn-primary">Mijn Orders</a>
                <a href="/order-nieuw" class="btn btn-secondary">Nieuwe Order</a>
            </div>
            """
            html += get_page_footer()
            logging.info(f"GET / van {self.client_address[0]}")
            send_html_response(self, 200, html)
            return

        # --------- MIJN ORDERS ---------
        if path == "/orders":
            if not walletid:
                send_redirect(self, "/inloggen?redirect=/orders")
                return

            wallet = get_wallet_by_id(walletid)
            orders = get_wallet_orders(walletid)

            html = get_page_header()
            html += f"""
            <div class="header">
                <h1>CryptoPortal</h1>
                <p class="subtitle">Portefeuille {walletid}</p>
            </div>

            <div class="breadcrumb">
                <a href="/">Home</a> / Mijn Orders
            </div>

            <div class="orders-section">
                <h2>Mijn Orders ({len(orders)})</h2>
            """

            if orders:
                html += '<table class="orders-table">'
                html += """
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Asset</th>
                        <th>Type</th>
                        <th>Prijs</th>
                        <th>Hoeveelheid</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                """
                for order in orders:
                    status_class = "status-" + order[7].lower().replace(" ", "-")
                    html += f"""
                    <tr>
                        <td class="order-id">{order[0]}</td>
                        <td>{order[1]} ({order[2]})</td>
                        <td><span class="badge {('badge-buy' if order[3] == 'Koop' else 'badge-sell')}">{order[3]}</span></td>
                        <td>{order[4]} {order[5]}</td>
                        <td>{order[6]}</td>
                        <td><span class="{status_class}">{order[7]}</span></td>
                    </tr>
                    """
                html += "</tbody></table>"
            else:
                html += '<p class="no-orders">Geen orders gevonden</p>'

            html += """
            </div>

            <div class="action-links">
                <a href="/order-nieuw" class="btn btn-primary">Nieuwe Order</a>
                <a href="/uitloggen" class="btn btn-danger">Uitloggen</a>
            </div>
            """
            html += get_page_footer()
            send_html_response(self, 200, html)
            return

        # --------- INLOGGEN (REDIRECT) ---------
        if path == "/inloggen":
            redirect = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('redirect', ['/orders'])[0]
            html = get_page_header()
            html += f"""
            <div class="header">
                <h1>CryptoPortal</h1>
                <p class="subtitle">Veilig Inloggen</p>
            </div>

            <div class="login-box">
                <h2>Portefeuille Toegang</h2>
                <p class="login-hint">Voer je portefeuille-ID en PIN in</p>
                <form method="POST" action="/inloggen">
                    <input type="hidden" name="redirect" value="{html_escape(redirect)}">
                    
                    <div class="form-group">
                        <label for="walletid">Portefeuille ID</label>
                        <input 
                            type="number" 
                            id="walletid"
                            name="walletid" 
                            required 
                            placeholder="bijv. "
                            min="100"
                            max="999"
                        >
                    </div>

                    <div class="form-group">
                        <label for="pin">PIN Code</label>
                        <input 
                            type="password" 
                            id="pin"
                            name="pin" 
                            required 
                            placeholder="Vul je PIN in"
                            maxlength="6"
                        >
                    </div>

                    <button type="submit" class="btn btn-primary full-width">Inloggen</button>
                </form>
            </div>

           
            """
            html += get_page_footer()
            send_html_response(self, 200, html)
            return

        # --------- NIEUWE ORDER ---------
        if path == "/order-nieuw":
            if not walletid:
                send_redirect(self, "/inloggen?redirect=/order-nieuw")
                return

            wallet = get_wallet_by_id(walletid)
            cryptos = get_crypto_list()

            crypto_options = "".join([
                f'<option value="{c[0]}">{c[1]} ({c[2]})</option>'
                for c in cryptos
            ])

            html = get_page_header()
            html += f"""
            <div class="header">
                <h1>CryptoPortal</h1>
                <p class="subtitle">Nieuwe Order Plaatsen</p>
            </div>

            <div class="breadcrumb">
                <a href="/">Home</a> / <a href="/orders">Mijn Orders</a> / Nieuwe Order
            </div>

            <div class="order-form-section">
                <h2>Order Details</h2>
                <p class="wallet-info">Portefeuille: <strong>{wallet[0]}</strong> | {wallet[1]}</p>

                <form method="POST" action="/order-nieuw" class="order-form">
                    <div class="form-group">
                        <label for="cryptoid">Cryptocurrency</label>
                        <select id="cryptoid" name="cryptoid" required>
                            <option value="">-- Selecteer cryptocurrency --</option>
                            {crypto_options}
                        </select>
                    </div>

                    <div class="form-row">
                        <div class="form-group">
                            <label for="zijde">Type Order</label>
                            <select id="zijde" name="zijde" required>
                                <option value="Koop">Koop</option>
                                <option value="Verkoop">Verkoop</option>
                            </select>
                        </div>

                        <div class="form-group">
                            <label for="munteenheid">Munt</label>
                            <select id="munteenheid" name="munteenheid" required>
                                <option value="EUR">EUR (Euro)</option>
                                <option value="USD">USD (Dollar)</option>
                                <option value="GBP">GBP (Pond)</option>
                            </select>
                        </div>
                    </div>

                    <div class="form-row">
                        <div class="form-group">
                            <label for="prijs">Prijs</label>
                            <input 
                                type="number" 
                                id="prijs"
                                name="prijs" 
                                required 
                                step="0.01"
                                min="0.01"
                                placeholder="0.00"
                            >
                        </div>

                        <div class="form-group">
                            <label for="hoeveelheid">Hoeveelheid</label>
                            <input 
                                type="number" 
                                id="hoeveelheid"
                                name="hoeveelheid" 
                                required 
                                step="1"
                                min="1"
                                placeholder="0"
                            >
                        </div>
                    </div>

                    <div class="button-group">
                        <button type="submit" class="btn btn-primary">Order Plaatsen</button>
                        <a href="/orders" class="btn btn-secondary">Annuleren</a>
                    </div>
                </form>
            </div>
            """
            html += get_page_footer()
            send_html_response(self, 200, html)
            return

        # --------- UITLOGGEN ---------
        if path == "/uitloggen":
            cookie = self.headers.get("Cookie", "")
            if "sessie=" in cookie:
                sid = cookie.split("sessie=")[1].split(";")[0]
                SESSIONS.pop(sid, None)
                logging.info(f"Uitloggen - sessie: {sid}")

            send_redirect(self, "/")
            return

        # --------- 404 ---------
        html = get_page_header()
        html += """
        <div class="error-box">
            <h1>404</h1>
            <p>Pagina niet gevonden</p>
            <a href="/" class="btn btn-primary">Terug naar Home</a>
        </div>
        """
        html += get_page_footer()
        send_html_response(self, 404, html)

    # ===== POST =====
    def do_POST(self):
        """Verwerkt POST requests"""
        path = urllib.parse.urlparse(self.path).path
        data = read_post_data(self)

        # --------- INLOGGEN ---------
        if path == "/inloggen":
            walletid_str = data.get("walletid", [""])[0]
            pin = data.get("pin", [""])[0]
            redirect = data.get("redirect", ["/orders"])[0]

            if not walletid_str or not pin:
                logging.warning(f"Inlog poging zonder walletid/pin van {self.client_address[0]}")
                send_redirect(self, f"/inloggen?redirect={redirect}&error=1")
                return

            try:
                walletid = int(walletid_str)
            except ValueError:
                logging.warning(f"Ongeldige walletid: {walletid_str}")
                send_redirect(self, f"/inloggen?redirect={redirect}&error=1")
                return

            if not get_wallet_by_id(walletid):
                logging.warning(f"Inlog poging met onbekende walletid: {walletid}")
                send_redirect(self, f"/inloggen?redirect={redirect}&error=1")
                return

            if not verify_pin(walletid, pin):
                logging.warning(f"Ongeldige PIN voor walletid {walletid} van {self.client_address[0]}")
                send_redirect(self, f"/inloggen?redirect={redirect}&error=2")
                return

            # PIN juist - sessie aanmaken
            sid = str(uuid.uuid4())
            SESSIONS[sid] = {
                'walletid': walletid,
                'timestamp': datetime.now()
            }
            logging.info(f"Inloggen succesvol - Portefeuille: {walletid}, Sessie: {sid}")

            send_redirect(self, redirect, session_id=sid)
            return

        # --------- NIEUWE ORDER AANMAKEN ---------
        if path == "/order-nieuw":
            walletid = get_session(self)

            if not walletid:
                send_redirect(self, "/inloggen?redirect=/order-nieuw")
                return

            try:
                cryptoid = int(data.get("cryptoid", ["1"])[0])
                zijde = data.get("zijde", ["Koop"])[0]
                prijs = float(data.get("prijs", ["0"])[0])
                munteenheid = data.get("munteenheid", ["EUR"])[0]
                hoeveelheid = int(data.get("hoeveelheid", ["0"])[0])

                # Validatie
                if prijs <= 0 or hoeveelheid <= 0:
                    raise ValueError("Prijs en hoeveelheid moeten groter zijn dan 0")

                if create_order(walletid, cryptoid, zijde, prijs, munteenheid, hoeveelheid):
                    send_redirect(self, "/orders")
                    return

            except (ValueError, TypeError) as e:
                logging.error(f"Fout bij orderaanmaak: {e}")

            send_redirect(self, "/order-nieuw?error=1")
            return

        # --------- ONBEKENDE POST ---------
        send_html_response(self, 404, "<h1>404</h1><p>Niet gevonden</p>")


# =====================================================
# SERVER STARTEN
# =====================================================

if __name__ == "__main__":
    httpd = HTTPServer((HOST, PORT), Handler)
    logging.info(f"CryptoPortal gestart op http://{HOST}:{PORT}")
    print(f"CryptoPortal draait op http://localhost:{PORT}")
    print("Druk Ctrl+C om af te sluiten")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logging.info("Server gestopt")
        print("\nServer gestopt")