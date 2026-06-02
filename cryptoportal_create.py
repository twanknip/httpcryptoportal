#!/usr/bin/python3

import os
import sqlite3
import bcrypt

# Maak de data-map automatisch aan
os.makedirs("data", exist_ok=True)

DB_FILE = "data/cryptoportal.db"

con = sqlite3.connect(DB_FILE)
cur = con.cursor()

# =====================================================
# WALLET TABEL
# =====================================================

cur.execute("DROP TABLE IF EXISTS wallet")

cur.execute("""
CREATE TABLE wallet (
    id INTEGER PRIMARY KEY,
    pincode TEXT NOT NULL,
    eigenaar TEXT NOT NULL
)
""")

# PINs: 314, 159, 265, 358
# Bcrypt hashes aanmaken (werk: $2b$12$ voor bcrypt identificatie)
wallets = [
    (314, bcrypt.hashpw(b"314", bcrypt.gensalt()).decode(), "Portefeuille 1"),
    (159, bcrypt.hashpw(b"159", bcrypt.gensalt()).decode(), "Portefeuille 2"),
    (265, bcrypt.hashpw(b"265", bcrypt.gensalt()).decode(), "Portefeuille 3"),
    (358, bcrypt.hashpw(b"358", bcrypt.gensalt()).decode(), "Portefeuille 4"),
]

cur.executemany(
    "INSERT INTO wallet (id, pincode, eigenaar) VALUES (?, ?, ?)",
    wallets
)

print("\n=== PORTEFEUILLES ===")
for row in cur.execute("SELECT id, eigenaar FROM wallet"):
    print(f"ID: {row[0]} | {row[1]}")

# =====================================================
# CRYPTO TABEL
# =====================================================

cur.execute("DROP TABLE IF EXISTS crypto")

cur.execute("""
CREATE TABLE crypto (
    id INTEGER PRIMARY KEY,
    naam TEXT NOT NULL,
    symbool TEXT NOT NULL
)
""")

cryptos = [
    (1, "Bitcoin", "BTC"),
    (2, "Ethereum", "ETH"),
    (3, "Tether", "USDT"),
    (4, "USD Coin", "USDC")
]

cur.executemany(
    "INSERT INTO crypto (id, naam, symbool) VALUES (?, ?, ?)",
    cryptos
)

print("\n=== CRYPTOCURRENCY ===")
for row in cur.execute("SELECT id, naam, symbool FROM crypto"):
    print(f"{row[0]}. {row[1]} ({row[2]})")

# =====================================================
# ORDERBOEK TABEL
# =====================================================

cur.execute("DROP TABLE IF EXISTS orderbook")

cur.execute("""
CREATE TABLE orderbook (
    id INTEGER PRIMARY KEY,
    walletid INTEGER NOT NULL,
    cryptoid INTEGER NOT NULL,
    zijde TEXT NOT NULL,
    prijs REAL NOT NULL,
    munteenheid TEXT NOT NULL,
    hoeveelheid INTEGER NOT NULL,
    status TEXT NOT NULL,
    datum_aangemaakt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(walletid) REFERENCES wallet(id),
    FOREIGN KEY(cryptoid) REFERENCES crypto(id)
)
""")

orders = [
    (1, 314, 1, "Koop", 89535, "EUR", 2, "NIEUW"),
    (2, 314, 1, "Verkoop", 89546, "EUR", 2, "NIEUW"),
    (3, 314, 2, "Koop", 3270, "EUR", 17, "NIEUW"),
    (4, 159, 2, "Koop", 3269, "EUR", 27, "NIEUW"),
    (5, 159, 3, "Koop", 1, "USD", 20000, "NIEUW"),
    (6, 159, 3, "Verkoop", 2, "USD", 12000, "NIEUW"),
    (7, 265, 1, "Koop", 74403, "GBP", 2, "NIEUW"),
    (8, 265, 1, "Verkoop", 74567, "GBP", 6, "NIEUW"),
    (9, 265, 1, "Verkoop", 73987, "GBP", 5, "NIEUW"),
    (10, 358, 4, "Koop", 7, "USD", 30000, "NIEUW"),
    (11, 358, 4, "Verkoop", 6, "USD", 25000, "NIEUW"),
    (12, 358, 4, "Koop", 6, "USD", 10000, "NIEUW")
]

cur.executemany(
    """
    INSERT INTO orderbook
    (id, walletid, cryptoid, zijde, prijs, munteenheid, hoeveelheid, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
    orders
)

print("\n=== ORDERBOEK ===")
for row in cur.execute("SELECT id, walletid, zijde, status FROM orderbook"):
    print(f"Order {row[0]} | Portefeuille {row[1]} | {row[2]} | Status: {row[3]}")

con.commit()
cur.close()
con.close()

print(f"\nDatabase succesvol aangemaakt: {DB_FILE}")
print("\nTest PIN-codes:")
print("  Portefeuille 314: PIN 314")
print("  Portefeuille 159: PIN 159")
print("  Portefeuille 265: PIN 265")
print("  Portefeuille 358: PIN 358")