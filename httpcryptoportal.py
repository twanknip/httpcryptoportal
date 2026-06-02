#!/usr/bin/python3

from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import sqlite3
from html import escape as html_escape
import bcrypt
import uuid
import json
import logging
import secrets
from datetime import datetime, timedelta
from collections import defaultdict
import time

# =====================================================
# SECURITY CONSTANTS
# =====================================================

LOGIN_ATTEMPTS = defaultdict(list)
MAX_ATTEMPTS = 5
BLOCK_TIME = 300
CLEANUP_INTERVAL = 300  # Clean expired sessions every 5 minutes
LAST_CLEANUP = time.time()

# =====================================================
# CONFIGURATIE
# =====================================================

LOG_FILE = "data/cryptoportal.log"
DB_FILE = "data/cryptoportal.db"
HOST = "0.0.0.0"
PORT = 8080
SESSION_TIMEOUT = 3600  # 1 uur
SESSION_ROTATION_TIME = 1800  # Rotate session every 30 minutes

# Allowed enums for input validation
ALLOWED_SIDES = {"Koop", "Verkoop"}
ALLOWED_CURRENCIES = {"EUR", "USD", "GBP"}

# Logging setup
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# =====================================================
# SESSIONS
# =====================================================

SESSIONS = {}  # session_id -> {
               #   'walletid': id,
               #   'timestamp': time,
               #   'ip': ip_address,
               #   'csrf_token': token,
               #   'rotated_at': time
               # }

CSRF_TOKENS = {}  # csrf_token -> expiration_time


# =====================================================
# SESSION MANAGEMENT
# =====================================================

def cleanup_expired_sessions():
    """Removes expired sessions periodically"""
    global LAST_CLEANUP
    now = time.time()
    
    if now - LAST_CLEANUP < CLEANUP_INTERVAL:
        return
    
    expired = [
        sid for sid, data in SESSIONS.items()
        if (now - data['timestamp'].timestamp()) > SESSION_TIMEOUT
    ]
    
    for sid in expired:
        SESSIONS.pop(sid, None)
        logging.info(f"Session expired and cleaned: {sid[:8]}...")
    
    LAST_CLEANUP = now


def is_session_valid(session_data, current_ip):
    """Validates session expiration and IP binding"""
    if not session_data:
        return False
    
    elapsed = (datetime.now() - session_data['timestamp']).total_seconds()
    
    # Check expiration
    if elapsed > SESSION_TIMEOUT:
        return False
    
    # Check IP binding (prevent session hijacking)
    if session_data.get('ip') != current_ip:
        return False
    
    return True


def create_session(walletid, ip_address):
    """Creates a new secure session"""
    sid = str(uuid.uuid4())
    csrf_token = secrets.token_urlsafe(32)
    
    SESSIONS[sid] = {
        'walletid': walletid,
        'timestamp': datetime.now(),
        'ip': ip_address,
        'csrf_token': csrf_token,
        'rotated_at': datetime.now()
    }
    
    CSRF_TOKENS[csrf_token] = datetime.now() + timedelta(hours=1)
    
    return sid, csrf_token


def rotate_session(session_id, ip_address):
    """Rotates session token (called periodically or on sensitive actions)"""
    if session_id not in SESSIONS:
        return None
    
    session_data = SESSIONS[session_id]
    elapsed = (datetime.now() - session_data['rotated_at']).total_seconds()
    
    if elapsed > SESSION_ROTATION_TIME:
        new_sid = str(uuid.uuid4())
        new_csrf_token = secrets.token_urlsafe(32)
        
        session_data['rotated_at'] = datetime.now()
        session_data['timestamp'] = datetime.now()  # Refresh timestamp too
        
        SESSIONS[new_sid] = session_data
        CSRF_TOKENS[new_csrf_token] = datetime.now() + timedelta(hours=1)
        
        SESSIONS.pop(session_id, None)
        logging.info(f"Session rotated: {session_id[:8]}...")
        
        return new_sid, new_csrf_token
    
    return session_id, session_data['csrf_token']


# =====================================================
# DATABASE FUNCTIONS
# =====================================================

def get_db():
    con = sqlite3.connect(DB_FILE)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def get_wallet_by_id(walletid):
    """Haalt portefeuille gegevens op"""
    try:
        if not isinstance(walletid, int) or walletid < 0:
            return None
        
        con = get_db()
        cur = con.cursor()
        result = cur.execute(
            "SELECT id, eigenaar FROM wallet WHERE id = ?",
            (walletid,)
        ).fetchone()
        con.close()
        return result
    except Exception as e:
        logging.error(f"Database error in get_wallet_by_id: {type(e).__name__}")
        return None


def verify_pin(walletid, pin):
    """Verifieert PIN met bcrypt"""
    try:
        if not isinstance(walletid, int) or walletid < 0:
            return False
        
        if not isinstance(pin, str) or len(pin) == 0:
            return False
        
        con = get_db()
        cur = con.cursor()
        result = cur.execute(
            "SELECT pincode FROM wallet WHERE id = ?",
            (walletid,)
        ).fetchone()
        con.close()

        if not result:
            return False

        # Constant-time comparison to prevent timing attacks
        return bcrypt.checkpw(pin.encode(), result[0].encode())
    except Exception as e:
        logging.error(f"PIN verification error: {type(e).__name__}")
        return False


def get_crypto_list():
    """Haalt alle beschikbare cryptocurrencies op"""
    try:
        con = get_db()
        cur = con.cursor()
        result = cur.execute(
            "SELECT id, naam, symbool FROM crypto ORDER BY id"
        ).fetchall()
        con.close()
        return result
    except Exception as e:
        logging.error(f"Database error in get_crypto_list: {type(e).__name__}")
        return []


def get_crypto_by_id(cryptoid):
    """Haalt cryptocurrency op en valideert deze bestaat"""
    try:
        if not isinstance(cryptoid, int) or cryptoid < 0:
            return None
        
        con = get_db()
        cur = con.cursor()
        result = cur.execute(
            "SELECT id, naam, symbool FROM crypto WHERE id = ?",
            (cryptoid,)
        ).fetchone()
        con.close()
        return result
    except Exception as e:
        logging.error(f"Database error in get_crypto_by_id: {type(e).__name__}")
        return None


def get_wallet_orders(walletid):
    """Haalt alle orders voor een portefeuille op"""
    try:
        if not isinstance(walletid, int) or walletid < 0:
            return []
        
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
    except Exception as e:
        logging.error(f"Database error in get_wallet_orders: {type(e).__name__}")
        return []


def create_order(walletid, cryptoid, zijde, prijs, munteenheid, hoeveelheid):
    """Maakt een nieuwe order aan met strikte validatie"""
    try:
        # Strict input validation
        if not isinstance(walletid, int) or walletid < 0:
            return False
        
        if not isinstance(cryptoid, int) or cryptoid < 0:
            return False
        
        if zijde not in ALLOWED_SIDES:
            logging.warning(f"Invalid side attempted: {zijde}")
            return False
        
        if munteenheid not in ALLOWED_CURRENCIES:
            logging.warning(f"Invalid currency attempted: {munteenheid}")
            return False
        
        if not isinstance(prijs, (int, float)) or prijs <= 0:
            return False
        
        if not isinstance(hoeveelheid, int) or hoeveelheid <= 0:
            return False
        
        # Verify crypto exists
        if not get_crypto_by_id(cryptoid):
            return False
        
        con = get_db()
        cur = con.cursor()
        cur.execute("""
            INSERT INTO orderbook 
            (walletid, cryptoid, zijde, prijs, munteenheid, hoeveelheid, status)
            VALUES (?, ?, ?, ?, ?, ?, 'NIEUW')
        """, (walletid, cryptoid, zijde, prijs, munteenheid, hoeveelheid))
        con.commit()
        con.close()
        
        logging.info(f"Order created - Wallet: {walletid}, Crypto: {cryptoid}")
        return True
    except Exception as e:
        logging.error(f"Error creating order: {type(e).__name__}")
        return False


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def is_blocked(ip, walletid):
    """Check if IP is blocked due to too many failed login attempts"""
    try:
        if not isinstance(walletid, int):
            return True
        
        key = (ip, walletid)
        attempts = LOGIN_ATTEMPTS[key]
        
        # Remove old attempts
        now = time.time()
        attempts[:] = [t for t in attempts if now - t < BLOCK_TIME]
        
        return len(attempts) >= MAX_ATTEMPTS
    except Exception as e:
        logging.error(f"Error in is_blocked: {type(e).__name__}")
        return True


def register_failed_attempt(ip, walletid):
    """Register a failed login attempt"""
    try:
        if isinstance(walletid, int):
            key = (ip, walletid)
            LOGIN_ATTEMPTS[key].append(time.time())
            logging.warning(f"Failed login attempt from {ip}")
    except Exception:
        pass


def read_post_data(handler):
    """Leest POST data uit request met size limit"""
    try:
        length = int(handler.headers.get("Content-Length", 0))
        if length > 4096:  # Prevent large POST attacks
            return {}
        body = handler.rfile.read(length).decode('utf-8', errors='ignore')
        return urllib.parse.parse_qs(body)
    except Exception as e:
        logging.error(f"POST data read error: {type(e).__name__}")
        return {}


def get_session(handler):
    """Haalt session ID uit cookie en valideert deze"""
    try:
        cleanup_expired_sessions()
        
        cookie = handler.headers.get("Cookie", "")
        for part in cookie.split(";"):
            if "sessie=" in part:
                sid = part.split("=")[1].strip()
                if sid in SESSIONS:
                    session_data = SESSIONS[sid]
                    if is_session_valid(session_data, handler.client_address[0]):
                        return session_data['walletid']
                    else:
                        # Invalid session - remove it
                        SESSIONS.pop(sid, None)
    except Exception as e:
        logging.error(f"Session validation error: {type(e).__name__}")
    
    return None


def validate_csrf_token(data):
    """Validates CSRF token from POST data"""
    try:
        token = data.get("csrf_token", [""])[0]
        
        if not token or token not in CSRF_TOKENS:
            return False
        
        # Check if token has expired
        if datetime.now() > CSRF_TOKENS[token]:
            CSRF_TOKENS.pop(token, None)
            return False
        
        # Consume token (one-time use)
        CSRF_TOKENS.pop(token, None)
        return True
    except Exception:
        return False


def send_html_response(handler, status_code, html_content):
    """Stuurt HTML response met security headers"""
    handler.send_response(status_code)
    handler.send_header("Content-type", "text/html; charset=utf-8")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("X-Frame-Options", "DENY")
    handler.send_header("X-XSS-Protection", "1; mode=block")
    handler.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
    handler.end_headers()
    handler.wfile.write(html_content.encode("utf-8"))


def send_redirect(handler, location, session_id=None):
    """Stuurt redirect response"""
    handler.send_response(302)
    handler.send_header("X-Content-Type-Options", "nosniff")
    
    if session_id:
        handler.send_header("Set-Cookie", 
            f"sessie={session_id}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age={SESSION_TIMEOUT}")
    
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
        <meta http-equiv="X-UA-Compatible" content="ie=edge">
        <meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'self'">
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


def get_csrf_field(csrf_token):
    """Returns HTML hidden field with CSRF token"""
    return f'<input type="hidden" name="csrf_token" value="{html_escape(csrf_token)}">'


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
                    self.send_header("X-Content-Type-Options", "nosniff")
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
            logging.info(f"GET / from {self.client_address[0]}")
            send_html_response(self, 200, html)
            return

        # --------- MIJN ORDERS ---------
        if path == "/orders":
            if not walletid:
                send_redirect(self, "/inloggen?redirect=/orders")
                return

            wallet = get_wallet_by_id(walletid)
            if not wallet:
                send_redirect(self, "/inloggen")
                return

            orders = get_wallet_orders(walletid)

            html = get_page_header()
            html += f"""
            <div class="header">
                <h1>CryptoPortal</h1>
                <p class="subtitle">Portefeuille {html_escape(str(walletid))}</p>
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
                    status_class = "status-" + html_escape(order[7]).lower().replace(" ", "-")
                    html += f"""
                    <tr>
                        <td class="order-id">{html_escape(str(order[0]))}</td>
                        <td>{html_escape(order[1])} ({html_escape(order[2])})</td>
                        <td><span class="badge {('badge-buy' if order[3] == 'Koop' else 'badge-sell')}">{html_escape(order[3])}</span></td>
                        <td>{html_escape(str(order[4]))} {html_escape(order[5])}</td>
                        <td>{html_escape(str(order[6]))}</td>
                        <td><span class="{status_class}">{html_escape(order[7])}</span></td>
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
            try:
                redirect = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('redirect', ['/orders'])[0]
                # Validate redirect URL (prevent open redirect)
                if not redirect.startswith('/'):
                    redirect = '/orders'
            except:
                redirect = '/orders'
            
            # Generate new CSRF token for this request
            csrf_token = secrets.token_urlsafe(32)
            CSRF_TOKENS[csrf_token] = datetime.now() + timedelta(hours=1)
            
            html = get_page_header()
            html += f"""
            <div class="header">
                <h1>CryptoPortal</h1>
                <p class="subtitle">Veilig Inloggen</p>
            </div>

            <div class="login-box">
                <h2>Portefeuille Toegang</h2>
                <p class="login-hint">Voer je portefeuille-ID en PIN in</p>
                <form method="POST" action="/inloggen" class="login-form">
                    {get_csrf_field(csrf_token)}
                    <input type="hidden" name="redirect" value="{html_escape(redirect)}">
                    
                    <div class="form-group">
                        <label for="walletid">Portefeuille ID</label>
                        <input 
                            type="number" 
                            id="walletid"
                            name="walletid" 
                            required 
                             placeholder="bijv.100"  "
                            min="1"
                            max="999999"
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
                            maxlength="20"
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
            if not wallet:
                send_redirect(self, "/inloggen")
                return

            cryptos = get_crypto_list()

            crypto_options = "".join([
                f'<option value="{html_escape(str(c[0]))}">{html_escape(c[1])} ({html_escape(c[2])})</option>'
                for c in cryptos
            ])

            # Generate CSRF token
            csrf_token = secrets.token_urlsafe(32)
            CSRF_TOKENS[csrf_token] = datetime.now() + timedelta(hours=1)

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
                <p class="wallet-info">Portefeuille: <strong>{html_escape(str(wallet[0]))}</strong> | {html_escape(wallet[1])}</p>

                <form method="POST" action="/order-nieuw" class="order-form">
                    {get_csrf_field(csrf_token)}
                    
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
                                max="999999.99"
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
                                max="999999"
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
                try:
                    sid = cookie.split("sessie=")[1].split(";")[0]
                    SESSIONS.pop(sid, None)
                    logging.info(f"Logout")
                except:
                    pass

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
        ip = self.client_address[0]

        # --------- INLOGGEN ---------
        if path == "/inloggen":
            # Validate CSRF token
            if not validate_csrf_token(data):
                logging.warning(f"CSRF token validation failed for login from {ip}")
                send_redirect(self, "/inloggen?error=csrf")
                return

            walletid_str = data.get("walletid", [""])[0]
            pin = data.get("pin", [""])[0]
            redirect = data.get("redirect", ["/orders"])[0]

            # Validate redirect URL
            if not redirect.startswith('/'):
                redirect = '/orders'

            if not walletid_str or not pin:
                logging.warning(f"Login attempt without walletid/pin from {ip}")
                send_redirect(self, f"/inloggen?redirect={urllib.parse.quote(redirect)}&error=1")
                return

            try:
                walletid = int(walletid_str)
            except ValueError:
                logging.warning(f"Invalid walletid format from {ip}")
                send_redirect(self, f"/inloggen?redirect={urllib.parse.quote(redirect)}&error=1")
                return

            # =====================================================
            # BRUTE FORCE PROTECTION
            # =====================================================

            if is_blocked(ip, walletid):
                logging.warning(f"Blocked login attempt from {ip}")
                send_redirect(self, "/inloggen?error=blocked")
                return

            if not get_wallet_by_id(walletid):
                register_failed_attempt(ip, walletid)
                send_redirect(self, f"/inloggen?redirect={urllib.parse.quote(redirect)}&error=1")
                return

            if not verify_pin(walletid, pin):
                register_failed_attempt(ip, walletid)
                send_redirect(self, f"/inloggen?redirect={urllib.parse.quote(redirect)}&error=2")
                return

            # --------- SUCCESVOLLE LOGIN ---------
            sid, csrf_token = create_session(walletid, ip)
            
            logging.info(f"Successful login")

            send_redirect(self, redirect, session_id=sid)
            return

        # --------- NIEUWE ORDER AANMAKEN ---------
        if path == "/order-nieuw":
            walletid = get_session(self)

            if not walletid:
                send_redirect(self, "/inloggen?redirect=/order-nieuw")
                return

            # Validate CSRF token
            if not validate_csrf_token(data):
                logging.warning(f"CSRF token validation failed for order from user {walletid}")
                send_redirect(self, "/order-nieuw?error=csrf")
                return

            try:
                cryptoid = int(data.get("cryptoid", ["1"])[0])
                zijde = data.get("zijde", ["Koop"])[0].strip()
                prijs = float(data.get("prijs", ["0"])[0])
                munteenheid = data.get("munteenheid", ["EUR"])[0].strip()
                hoeveelheid = int(data.get("hoeveelheid", ["0"])[0])

                # Strict validation
                if prijs <= 0 or hoeveelheid <= 0:
                    raise ValueError("Prijs en hoeveelheid moeten groter zijn dan 0")

                if create_order(walletid, cryptoid, zijde, prijs, munteenheid, hoeveelheid):
                    send_redirect(self, "/orders")
                    return

            except (ValueError, TypeError) as e:
                logging.error(f"Order creation error: {type(e).__name__}")

            send_redirect(self, "/order-nieuw?error=1")
            return

        # --------- ONBEKENDE POST ---------
        send_html_response(self, 404, "<h1>404</h1><p>Niet gevonden</p>")


# =====================================================
# SERVER STARTEN
# =====================================================

if __name__ == "__main__":
    httpd = HTTPServer((HOST, PORT), Handler)
    logging.info(f"CryptoPortal started on http://{HOST}:{PORT}")
    print(f"CryptoPortal running on http://localhost:{PORT}")
    print("Press Ctrl+C to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logging.info("Server stopped")
        print("\nServer stopped")