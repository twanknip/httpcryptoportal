#!/usr/bin/python3

#
# SQLite programma voor het aanmaken van de CryptoPortal database
#

import os
import sqlite3

# Maak de data-map automatisch aan
os.makedirs("data", exist_ok=True)

DB_FILE = "data/cryptoportal.db"

con = sqlite3.connect(DB_FILE)
cur = con.cursor()

#
# Wallet tabel
#

cur.execute("DROP TABLE IF EXISTS wallet")

cur.execute("""
CREATE TABLE wallet (
    id INTEGER PRIMARY KEY,
    hash TEXT NOT NULL
)
""")

wallets = [
    (314, "642606e93992a316419e8b6081af73dd"),
    (159, "78085aa67eaa6d90ad7b067e5a05cd5e"),
    (265, "259a568c9e5262afa3bb020a24f9457e"),
    (358, "173bb7ab566b5ff777d6f6bc8cfd0e63"),
]

cur.executemany(
    "INSERT INTO wallet (id, hash) VALUES (?, ?)",
    wallets
)

print("\n=== WALLETS ===")
for row in cur.execute("SELECT * FROM wallet"):
    print(row)

#
# Crypto tabel
#

cur.execute("DROP TABLE IF EXISTS crypto")

cur.execute("""
CREATE TABLE crypto (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
)
""")

cryptos = [
    (1, "Bitcoin (BTC)"),
    (2, "Ethereum (ETH)"),
    (3, "Tether (USDT)"),
    (4, "USD Coin (USDC)")
]

cur.executemany(
    "INSERT INTO crypto (id, name) VALUES (?, ?)",
    cryptos
)

print("\n=== CRYPTO ===")
for row in cur.execute("SELECT * FROM crypto"):
    print(row)

#
# Orderboek tabel
#

cur.execute("DROP TABLE IF EXISTS orderbook")

cur.execute("""
CREATE TABLE orderbook (
    id INTEGER PRIMARY KEY,
    walletid INTEGER NOT NULL,
    cryptoid INTEGER NOT NULL,
    side TEXT NOT NULL,
    price INTEGER NOT NULL,
    currency TEXT NOT NULL,
    qty INTEGER NOT NULL,
    status TEXT NOT NULL,

    FOREIGN KEY(walletid) REFERENCES wallet(id),
    FOREIGN KEY(cryptoid) REFERENCES crypto(id)
)
""")

orders = [
    (1, 314, 1, "Buy", 89535, "EUR", 2, "NEW"),
    (2, 314, 1, "Sell", 89546, "EUR", 2, "NEW"),
    (3, 314, 2, "Buy", 3270, "EUR", 17, "NEW"),
    (4, 159, 2, "Buy", 3269, "EUR", 27, "NEW"),
    (5, 159, 3, "Buy", 1, "USD", 20000, "NEW"),
    (6, 159, 3, "Sell", 2, "USD", 12000, "NEW"),
    (7, 265, 1, "Buy", 74403, "GBP", 2, "NEW"),
    (8, 265, 1, "Sell", 74567, "GBP", 6, "NEW"),
    (9, 265, 1, "Sell", 73987, "GBP", 5, "NEW"),
    (10, 358, 4, "Buy", 7, "USD", 30000, "NEW"),
    (11, 358, 4, "Sell", 6, "USD", 25000, "NEW"),
    (12, 358, 4, "Buy", 6, "USD", 10000, "NEW")
]

cur.executemany(
    """
    INSERT INTO orderbook
    (id, walletid, cryptoid, side, price, currency, qty, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
    orders
)

print("\n=== ORDERBOOK ===")
for row in cur.execute("SELECT * FROM orderbook"):
    print(row)

con.commit()
cur.close()
con.close()

print("\nDatabase succesvol aangemaakt:")
print(DB_FILE)