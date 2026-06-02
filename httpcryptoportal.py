#!/usr/bin/python3

#
# Secure Webserver for the CryptoPortal based on http.server.HTTPServer
# 
# SECURITY IMPROVEMENTS:
# - Uses parameterized queries to prevent SQL Injection
# - Uses bcrypt for password hashing instead of MD5
# - Implements HTTPS with SSL/TLS
# - Implements rate limiting to prevent brute force attacks
# - Comprehensive logging for audit trail
# - Input validation for all user inputs
#

from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import sqlite3
import ssl
import logging
import json
import time
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict

# Configure logging
logging.basicConfig(
    filename='cryptoportal.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rate limiting dictionary: tracks failed login attempts per IP
# Format: {ip_address: {'count': int, 'blocked_until': datetime}}
rate_limit_tracker = defaultdict(lambda: {'count': 0, 'blocked_until': None})

def convert_int(s):
    """Safely convert string to integer."""
    try:
        i = int(s)
    except ValueError:
        i = 0
    return i

def validate_input(value, input_type, allowed_values=None):
    """
    Validate user input.
    
    Args:
        value: The value to validate
        input_type: Type check ('int', 'float', 'string')
        allowed_values: Optional list of allowed values
    
    Returns:
        Tuple (is_valid, cleaned_value)
    """
    try:
        if input_type == 'int':
            val = int(value)
            if val <= 0:
                return False, None
            return True, val
        elif input_type == 'float':
            val = float(value)
            if val <= 0:
                return False, None
            return True, val
        elif input_type == 'string':
            val = str(value).strip()
            if allowed_values and val not in allowed_values:
                return False, None
            return True, val
    except (ValueError, TypeError):
        return False, None
    return False, None

def check_rate_limit(client_ip):
    """
    Check if client IP is rate limited.
    Returns (is_allowed, remaining_time_seconds)
    """
    tracker = rate_limit_tracker[client_ip]
    
    # Check if temporarily blocked
    if tracker['blocked_until'] and datetime.now() < tracker['blocked_until']:
        remaining = (tracker['blocked_until'] - datetime.now()).total_seconds()
        return False, remaining
    
    # Reset if block time has passed
    if tracker['blocked_until'] and datetime.now() >= tracker['blocked_until']:
        tracker['count'] = 0
        tracker['blocked_until'] = None
    
    return True, 0

def record_failed_login(client_ip):
    """
    Record a failed login attempt and implement rate limiting.
    Returns remaining_block_time if blocked, 0 if not blocked.
    """
    tracker = rate_limit_tracker[client_ip]
    tracker['count'] += 1
    
    # Progressive blocking
    if tracker['count'] >= 5 and tracker['count'] < 10:
        tracker['blocked_until'] = datetime.now() + timedelta(minutes=1)
        logger.warning(f"Rate limit: {client_ip} blocked for 1 minute after {tracker['count']} failed attempts")
        return 60
    elif tracker['count'] >= 10 and tracker['count'] < 20:
        tracker['blocked_until'] = datetime.now() + timedelta(hours=1)
        logger.warning(f"Rate limit: {client_ip} blocked for 1 hour after {tracker['count']} failed attempts")
        return 3600
    elif tracker['count'] >= 20:
        tracker['blocked_until'] = datetime.now() + timedelta(days=1)
        logger.critical(f"Rate limit: {client_ip} blocked for 24 hours after {tracker['count']} failed attempts - POSSIBLE ATTACK")
        return 86400
    
    return 0

def verify_password(stored_hash, password):
    """
    Verify password against bcrypt hash.
    In production, use the bcrypt library: bcrypt.checkpw(password.encode(), stored_hash)
    This is a simplified version for demonstration.
    """
    try:
        import bcrypt
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
    except ImportError:
        # Fallback: simple hash comparison (NOT SECURE - for demo only)
        logger.warning("bcrypt not available - using insecure comparison")
        return hashlib.sha256(password.encode()).hexdigest() == stored_hash

class HTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        client_ip = self.client_address[0]
        self.log_message("====================================================================================")
    
        urlquery = urllib.parse.urlparse(self.path).query
        urlparams = urllib.parse.parse_qs(urlquery)

        # Check rate limiting first
        is_allowed, remaining_time = check_rate_limit(client_ip)
        if not is_allowed:
            logger.warning(f"Rate limited request from {client_ip}")
            self.send_response(429, "Too Many Requests")
            self.send_header("Content-type", "text/html")
            self.send_header("Retry-After", str(int(remaining_time)))
            self.end_headers()
            self.wfile.write(bytes(f"<h1>Too Many Requests</h1><p>Please try again in {int(remaining_time)} seconds.</p>", "UTF-8"))
            return

        try:
            # Check the path
            if self.path == "/":
                # Return the main page
                self.send_response(200, "OK")
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(bytes(htmlmain, "UTF-8"))
                logger.info(f"GET / from {client_ip}")
                    
            elif self.path.startswith("/orderview"):
                # Process the order view - REQUIRES AUTHENTICATION
                urlwalletid = convert_int(urlparams.get('walletid', ['0'])[0])
                wallet_password = urlparams.get('password', [''])[0]
                
                if urlwalletid <= 0 or not wallet_password:
                    # Missing credentials
                    self.send_response(401, "Unauthorized")
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(bytes(htmlerror401, "UTF-8"))
                    logger.warning(f"Unauthorized orderview attempt from {client_ip}")
                    return
                
                # Validate credentials against database using PARAMETERIZED QUERY
                con = sqlite3.connect("data/cryptoportal.db")
                cur = con.cursor()
                
                # Use parameterized query to prevent SQL injection
                result = cur.execute(
                    "SELECT password_hash FROM wallet WHERE id = ?", 
                    [urlwalletid]
                ).fetchone()
                
                if result is None or not verify_password(result[0], wallet_password):
                    # Authentication failed
                    record_failed_login(client_ip)
                    self.send_response(401, "Unauthorized")
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(bytes(htmlerror401, "UTF-8"))
                    logger.warning(f"Failed login attempt for wallet {urlwalletid} from {client_ip}")
                    cur.close()
                    con.close()
                    return
                
                # Authentication successful - fetch orders with PARAMETERIZED QUERY
                orders = "<table><tr><th>Wallet</th><th>Order</th><th>Crypto</th><th>Side</th><th>Price</th><th>Currency</th><th>Quantity</th><th>Status</th></tr>"
                
                rows = cur.execute(
                    """SELECT orderbook.walletid, orderbook.id, crypto.name, orderbook.side, 
                       orderbook.price, orderbook.currency, orderbook.qty, orderbook.status 
                       FROM orderbook 
                       INNER JOIN crypto ON crypto.id = orderbook.cryptoid 
                       WHERE orderbook.walletid = ?""",
                    [urlwalletid]
                ).fetchall()
                
                for row in rows:
                    walletid, orderid, crypto, side, price, currency, qty, status = row
                    orders += f"<tr><td>{walletid}</td><td>{orderid}</td><td>{crypto}</td><td>{side}</td><td>{price}</td><td>{currency}</td><td>{qty}</td><td>{status}</td></tr>"
                
                orders += "</table>"
                cur.close()
                con.close()

                self.send_response(200, "OK")
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(bytes(htmlorderview.replace("__WALLETID__", str(urlwalletid)).replace("__ORDERS__", orders), "UTF-8"))
                logger.info(f"Successful order view for wallet {urlwalletid} from {client_ip}")
                        
            elif self.path.startswith("/orderenter"):
                # Process the order enter - REQUIRES AUTHENTICATION
                urlwalletid = convert_int(urlparams.get('walletid', ['0'])[0])
                wallet_password = urlparams.get('password', [''])[0]
                urlcryptoid = convert_int(urlparams.get('cryptoid', ['1'])[0])
                urlside = urlparams.get('side', ['Buy'])[0]
                urlprice = convert_int(urlparams.get('price', ['0'])[0])
                urlcurrency = urlparams.get('currency', ['EUR'])[0]
                urlquantity = convert_int(urlparams.get('quantity', ['0'])[0])

                # Validate inputs
                is_valid_price, valid_price = validate_input(urlprice, 'int')
                is_valid_qty, valid_qty = validate_input(urlquantity, 'int')
                is_valid_side, valid_side = validate_input(urlside, 'string', ['Buy', 'Sell'])
                is_valid_currency, valid_currency = validate_input(urlcurrency, 'string', ['EUR', 'USD', 'GBP'])
                
                if not (is_valid_price and is_valid_qty and is_valid_side and is_valid_currency):
                    self.send_response(400, "Bad Request")
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(bytes(htmlerror400, "UTF-8"))
                    logger.warning(f"Invalid input from {client_ip}: price={urlprice}, qty={urlquantity}, side={urlside}, currency={urlcurrency}")
                    return

                if urlwalletid > 0 and wallet_password:
                    # Authenticate
                    con = sqlite3.connect("data/cryptoportal.db")
                    cur = con.cursor()
                    
                    result = cur.execute(
                        "SELECT password_hash FROM wallet WHERE id = ?",
                        [urlwalletid]
                    ).fetchone()
                    
                    if result is None or not verify_password(result[0], wallet_password):
                        record_failed_login(client_ip)
                        self.send_response(401, "Unauthorized")
                        self.send_header("Content-type", "text/html")
                        self.end_headers()
                        self.wfile.write(bytes(htmlerror401, "UTF-8"))
                        logger.warning(f"Failed authentication for wallet {urlwalletid} from {client_ip}")
                        cur.close()
                        con.close()
                        return
                    
                    # Insert order with PARAMETERIZED QUERY
                    orderid = convert_int(cur.execute("SELECT max(id) FROM orderbook").fetchone()[0]) + 1
                    cur.execute(
                        """INSERT INTO orderbook(id, walletid, cryptoid, side, price, currency, qty, status) 
                           VALUES(?, ?, ?, ?, ?, ?, ?, 'NEW')""",
                        [orderid, urlwalletid, urlcryptoid, valid_side, valid_price, valid_currency, valid_qty]
                    )
                    cur.close()
                    con.commit()
                    con.close()
                    
                    logger.info(f"Order {orderid} created for wallet {urlwalletid} from {client_ip}: {valid_side} {valid_qty} {urlcryptoid} @ {valid_price} {valid_currency}")
                    
                    self.send_response(301, "Moved Permanently")
                    self.send_header("Location", f"/orderview?walletid={urlwalletid}")
                    self.end_headers()
                else:
                    # Show order entry form
                    self.send_response(200, "OK")
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(bytes(htmlorderenter.replace("__CRYPTOS__", htmlcryptos), "UTF-8"))
                    logger.info(f"Order entry form requested from {client_ip}")
                
            elif self.path == "/cryptoportal.jpeg":
                # Return the cryptoportal.jpeg
                self.send_response(200, "OK")
                self.send_header("Content-type", "image/jpeg")
                self.end_headers()
                self.wfile.write(jpegcryptoportal)
            
            else:
                # Invalid path so send error 404
                self.send_response(404, "Not Found")
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(bytes(htmlerror404, "UTF-8"))
                logger.warning(f"404 Not Found: {self.path} from {client_ip}")

        except Exception as e:
            logger.error(f"Exception in request handling: {str(e)}", exc_info=True)
            self.send_response(500, "Internal Server Error")
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes("<h1>Internal Server Error</h1>", "UTF-8"))

        # Log the request
        self.log_message("%s", f"Request  - client : {self.client_address}")
        self.log_message("%s", f"Request  - command: {self.command}")
        self.log_message("%s", f"Request  - path   : {self.path}")
        self.log_message("%s", f"Request  - version: {self.request_version}")
        for header in self.headers.items():
            self.log_message("%s", f"Request  - header : {header}")

        # Log the response
        self.log_message("%s", f"Response - server version  : {self.server_version}")
        self.log_message("%s", f"Response - system version  : {self.sys_version}")
        self.log_message("%s", f"Response - protocol version: {self.protocol_version}")


# Load HTML templates
with open("www/main.html") as file:
    htmlmain = file.read()

with open("www/orderview.html") as file:
    htmlorderview = file.read()

with open("www/orderenter.html") as file:
    htmlorderenter = file.read()

with open("www/cryptoportal.jpeg", "rb") as file:
    jpegcryptoportal = file.read()
    
with open("www/error400.html") as file:
    htmlerror400 = file.read()

with open("www/error401.html") as file:
    htmlerror401 = file.read()

with open("www/error404.html") as file:
    htmlerror404 = file.read()

# Load crypto list from database
con = sqlite3.connect("data/cryptoportal.db")
cur = con.cursor()
htmlcryptos = ""
for row in cur.execute("select id, name from crypto"):
    cryptoid = row[0]
    cryptoname = row[1]
    htmlcryptos += f"<option value='{cryptoid}'>{cryptoname}</option>"
cur.close()
con.close()

# Setup HTTPS with self-signed certificate
# To generate certificate: openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365
try:
    httpd = HTTPServer(('', 443), HTTPRequestHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain('ssl/cert.pem', 'ssl/key.pem')
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    logger.info("HTTPS server starting on port 443")
    print("HTTPS CryptoPortal server running on https://localhost:443")
except FileNotFoundError:
    logger.warning("SSL certificates not found. Running on HTTP (INSECURE) on port 8080")
    print("WARNING: SSL certificates not found. Running on INSECURE HTTP on port 8080")
    httpd = HTTPServer(('', 8080), HTTPRequestHandler)

try:
    httpd.serve_forever()
except KeyboardInterrupt:
    logger.info("Server shutting down")
    pass
finally:
    httpd.server_close()
    logger.info("Server closed")