#!/usr/bin/python3

import sqlite3
import random
import logging
from datetime import datetime

# =====================================================
# CONFIGURATIE
# =====================================================

DB_FILE = "data/cryptoportal.db"
LOG_FILE = "data/cryptoportal.log"

# Logging instellen
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# =====================================================
# BEURZEN
# =====================================================

BEURZEN = [
    "Kraken",
    "KuCoin",
    "Binance",
    "Bitfinex",
    "Coinbase"
]

# =====================================================
# ORDERS VERWERKEN
# =====================================================

def process_orders():
    """Verwerkt alle nieuwe orders in het orderboek"""
    try:
        con = sqlite3.connect(DB_FILE)
        con.execute("PRAGMA foreign_keys = ON")
        cur = con.cursor()

        # Haal alle nieuwe orders op
        orders = cur.execute(
            "SELECT id FROM orderbook WHERE status = 'NIEUW'"
        ).fetchall()

        if not orders:
            logging.info("Geen nieuwe orders gevonden")
            return

        logging.info(f"Verwerken van {len(orders)} orders")

        # Verwerk elke order
        for order in orders:
            orderid = order[0]
            
            # Willekeurig resultaat bepalen
            keuze = random.randint(0, 4)
            
            if keuze == 0:
                status = "GEANNULEERD"
            else:
                beurs = BEURZEN[keuze - 1]
                status = f"UITGEVOERD op {beurs}"
            
            # Update order status
            cur.execute(
                "UPDATE orderbook SET status = ? WHERE id = ?",
                (status, orderid)
            )
            
            logging.info(f"Order {orderid}: {status}")

        con.commit()
        con.close()
        logging.info("Order verwerking voltooid")

    except Exception as e:
        logging.error(f"Fout bij order verwerking: {e}")


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":
    process_orders()