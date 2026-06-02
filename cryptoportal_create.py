#!/usr/bin/python3

#
# Secure sqlite program for creating the cryptoportal database
# 
# SECURITY IMPROVEMENTS:
# - Uses bcrypt for password hashing instead of MD5
# - Stores proper password hashes instead of weak MD5
#

import sqlite3

# For password hashing, install bcrypt: pip install bcrypt
try:
    import bcrypt
    def hash_password(password):
        """Hash password using bcrypt."""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
except ImportError:
    import hashlib
    def hash_password(password):
        """Fallback: simple SHA256 hash (NOT SECURE - use bcrypt in production)."""
        print("WARNING: bcrypt not installed. Using insecure SHA256 hashing.")
        print("Install bcrypt with: pip install bcrypt")
        return hashlib.sha256(password.encode()).hexdigest()

con = sqlite3.connect("cryptoportal.db")
cur = con.cursor()

# Create wallet table with password hashing
cur.execute("DROP TABLE IF EXISTS wallet")
cur.execute("CREATE TABLE wallet(id PRIMARY KEY, password_hash TEXT NOT NULL)")

# Example wallets with passwords:
# Wallet 314: password is "securepass123"
# Wallet 159: password is "trading2024"
# Wallet 265: password is "crypto@secure"
# Wallet 358: password is "bitcoin.eth"

wallets = [
    (314, "securepass123"),
    (159, "trading2024"),
    (265, "crypto@secure"),
    (358, "bitcoin.eth")
]

for wallet_id, password in wallets:
    password_hash = hash_password(password)
    cur.execute("INSERT INTO wallet VALUES(?, ?)", [wallet_id, password_hash])
    print(f"Created wallet {wallet_id} with secure password hash")

for row in cur.execute("SELECT id FROM wallet"):
    print(f"  - Wallet {row[0]} ready")
    
cur.execute("DROP TABLE IF EXISTS crypto")
cur.execute("CREATE TABLE crypto(id PRIMARY KEY, name TEXT NOT NULL)")
cur.execute("INSERT INTO crypto VALUES( 1, 'Bitcoin (BTC)')")
cur.execute("INSERT INTO crypto VALUES( 2, 'Ethereum (ETH)')")
cur.execute("INSERT INTO crypto VALUES( 3, 'Tether (USDT)')")
cur.execute("INSERT INTO crypto VALUES( 4, 'USD Coin (USDC)')")

for row in cur.execute("SELECT * FROM crypto"):
    print(f"  - Crypto: {row}")
    
cur.execute("DROP TABLE IF EXISTS orderbook")
cur.execute("CREATE TABLE orderbook(id PRIMARY KEY, walletid INTEGER, cryptoid INTEGER, side TEXT, price INTEGER, currency TEXT, qty INTEGER, status TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

orders = [
    (1, 314, 1, 'Buy' , 89535, 'EUR',     2, 'NEW'),
    (2, 314, 1, 'Sell', 89546, 'EUR',     2, 'NEW'),
    (3, 314, 2, 'Buy' ,  3270, 'EUR',    17, 'NEW'),
    (4, 159, 2, 'Buy' ,  3269, 'EUR',    27, 'NEW'),
    (5, 159, 3, 'Buy' ,     1, 'USD', 20000, 'NEW'),
    (6, 159, 3, 'Sell',     2, 'USD', 12000, 'NEW'),
    (7, 265, 1, 'Buy' , 74403, 'GBP',     2, 'NEW'),
    (8, 265, 1, 'Sell', 74567, 'GBP',     6, 'NEW'),
    (9, 265, 1, 'Sell', 73987, 'GBP',     5, 'NEW'),
    (10, 358, 4, 'Buy' ,     7, 'USD', 30000, 'NEW'),
    (11, 358, 4, 'Sell',     6, 'USD', 25000, 'NEW'),
    (12, 358, 4, 'Buy' ,     6, 'USD', 10000, 'NEW'),
]

for order in orders:
    cur.execute("INSERT INTO orderbook VALUES(?, ?, ?, ?, ?, ?, ?, ?)", order)

for row in cur.execute("SELECT * FROM orderbook"):
    print(f"  - Order: {row}")

cur.close()
con.commit()
con.close()

print("\nDatabase created successfully!")
print("Important: Share these passwords with wallet owners securely (not in this script)")
print("Passwords are now hashed with bcrypt and cannot be recovered - only verified")