#!/usr/bin/python3

"""
CryptoPortal Database Creation Script
Secure initialization with proper constraints and validation
"""

import sqlite3
import bcrypt
import os
import sys

# =====================================================
# CONFIGURATION
# =====================================================

DB_FILE = "data/cryptoportal.db"
DB_BACKUP = "data/cryptoportal.db.backup"

# Security settings
BCRYPT_ROUNDS = 12


# =====================================================
# DATABASE CREATION
# =====================================================

def create_database():
    """
    Creates the database schema with security constraints
    
    WARNING: This script uses DROP TABLE in development mode.
    In production, use proper migration tools instead.
    """
    
    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    # Backup existing database if it exists (safety measure)
    if os.path.exists(DB_FILE):
        print(f"[!] Database exists. Creating backup at {DB_BACKUP}")
        try:
            import shutil
            if os.path.exists(DB_BACKUP):
                os.remove(DB_BACKUP)
            shutil.copy2(DB_FILE, DB_BACKUP)
            print("[+] Backup created successfully")
        except Exception as e:
            print(f"[!] Could not create backup: {e}")
            print("[!] Aborting database creation to prevent data loss")
            return False
        
        # Only drop tables in development (careful!)
        print("[*] Dropping existing tables...")
    
    try:
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()
        
        # Enable foreign key constraints
        cur.execute("PRAGMA foreign_keys = ON")
        
        # ===== DROP EXISTING TABLES (DEVELOPMENT ONLY) =====
        # WARNING: This is destructive. In production, use migrations.
        print("[*] Creating fresh schema...")
        cur.execute("DROP TABLE IF EXISTS orderbook")
        cur.execute("DROP TABLE IF EXISTS crypto")
        cur.execute("DROP TABLE IF EXISTS wallet")
        
        # ===== WALLET TABLE =====
        cur.execute("""
            CREATE TABLE wallet (
                id INTEGER PRIMARY KEY,
                pincode TEXT NOT NULL,
                eigenaar TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add index for faster lookups
        cur.execute("CREATE INDEX idx_wallet_id ON wallet(id)")
        
        print("[+] Created wallet table")
        
        # ===== CRYPTO TABLE =====
        cur.execute("""
            CREATE TABLE crypto (
                id INTEGER PRIMARY KEY,
                naam TEXT NOT NULL UNIQUE,
                symbool TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cur.execute("CREATE INDEX idx_crypto_naam ON crypto(naam)")
        cur.execute("CREATE INDEX idx_crypto_symbool ON crypto(symbool)")
        
        print("[+] Created crypto table")
        
        # ===== ORDERBOOK TABLE =====
        cur.execute("""
            CREATE TABLE orderbook (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                walletid INTEGER NOT NULL,
                cryptoid INTEGER NOT NULL,
                zijde TEXT NOT NULL CHECK (zijde IN ('Koop', 'Verkoop')),
                prijs REAL NOT NULL CHECK (prijs > 0),
                munteenheid TEXT NOT NULL CHECK (munteenheid IN ('EUR', 'USD', 'GBP')),
                hoeveelheid INTEGER NOT NULL CHECK (hoeveelheid > 0),
                status TEXT NOT NULL DEFAULT 'NIEUW' CHECK (status IN ('NIEUW', 'UITGEVOERD', 'GEANNULEERD')),
                datum_aangemaakt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (walletid) REFERENCES wallet(id) ON DELETE RESTRICT,
                FOREIGN KEY (cryptoid) REFERENCES crypto(id) ON DELETE RESTRICT
            )
        """)
        
        # Add indexes for query performance
        cur.execute("CREATE INDEX idx_orderbook_walletid ON orderbook(walletid)")
        cur.execute("CREATE INDEX idx_orderbook_cryptoid ON orderbook(cryptoid)")
        cur.execute("CREATE INDEX idx_orderbook_datum ON orderbook(datum_aangemaakt)")
        
        print("[+] Created orderbook table")
        
        # ===== INSERT TEST DATA =====
        print("\n[*] Populating test data...")
        
        # Insert test cryptocurrencies
        cryptos = [
            ('Bitcoin', 'BTC'),
            ('Ethereum', 'ETH'),
            ('Tether', 'USDT'),
        ]
        
        for naam, symbool in cryptos:
            try:
                cur.execute(
                    "INSERT INTO crypto (naam, symbool) VALUES (?, ?)",
                    (naam, symbool)
                )
                print(f"[+] Inserted {naam} ({symbool})")
            except sqlite3.IntegrityError:
                print(f"[!] {naam} already exists, skipping")
        
        # Insert test wallets with hashed PINs
        # WARNING: These are test PINs only. In production, use proper key derivation.
        test_wallets = [
            (101, "5678"),  
            (102, "9012"),
            (103, "3456"),  
        ]
        
        for wallet_id, pin in test_wallets:
            try:
                # Hash the PIN using bcrypt (cost factor 12)
                pin_hash = bcrypt.hashpw(pin.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS))
                pin_hash_str = pin_hash.decode()
                
                # Use a generic owner name for test data
                owner_name = f" User {wallet_id}"
                
                cur.execute(
                    "INSERT INTO wallet (id, pincode, eigenaar) VALUES (?, ?, ?)",
                    (wallet_id, pin_hash_str, owner_name)
                )
                print(f"[+] Inserted wallet {wallet_id} (PIN: {pin})")
            except sqlite3.IntegrityError:
                print(f"[!] Wallet {wallet_id} already exists, skipping")
        
        # Commit changes
        con.commit()
        print("\n[+] Database creation successful!")
        print(f"[+] Database saved to {DB_FILE}")
        
        return True
        
    except Exception as e:
        print(f"[!] Error creating database: {e}")
        con.rollback()
        return False
    finally:
        con.close()


# =====================================================
# VERIFICATION
# =====================================================

def verify_database():
    """Verifies the database structure is correct"""
    try:
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()
        
        # Check tables exist
        cur.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('wallet', 'crypto', 'orderbook')
        """)
        tables = [row[0] for row in cur.fetchall()]
        
        if len(tables) != 3:
            print("[!] Not all required tables found")
            return False
        
        print("[+] All required tables exist")
        
        # Check wallet count
        cur.execute("SELECT COUNT(*) FROM wallet")
        wallet_count = cur.fetchone()[0]
        print(f"[+] Wallets in database: {wallet_count}")
        
        # Check crypto count
        cur.execute("SELECT COUNT(*) FROM crypto")
        crypto_count = cur.fetchone()[0]
        print(f"[+] Cryptocurrencies in database: {crypto_count}")
        
        con.close()
        return True
        
    except Exception as e:
        print(f"[!] Verification failed: {e}")
        return False


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":
    print("=" * 60)
    print("CryptoPortal Database Creation Script")
    print("=" * 60)
    print()
    
    if not create_database():
        print("\n[!] Database creation failed!")
        sys.exit(1)
    
    print()
    if verify_database():
        print("\n[+] Database is ready for use!")
        print("\n[*] Next steps:")
        print("    1. Copy www/ directory with HTML and CSS files")
        print("    2. Run: python3 httpcryptoportal.py")
        sys.exit(0)
    else:
        print("\n[!] Database verification failed!")
        sys.exit(1)