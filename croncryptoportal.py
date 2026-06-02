#! /usr/bin/python3

#
# cron-job for the CryptoPortal to process the orders
#

import sqlite3
import random

con = sqlite3.connect("data/cryptoportal.db")
cur = con.cursor()
rows = cur.execute("select id from orderbook where status = 'NEW'").fetchall()
for row in rows:
    orderid = row[0]
    
    match random.randint(0, 4):
        case 0:
            status = 'CANCELLED'
        case 1:
            status = 'EXECUTED on Kraken'
        case 2:
            status = 'EXECUTED on KuCoin'
        case 3:
            status = 'EXECUTED on Binance'
        case 4:
            status = 'EXECUTED on Bitfinex'
    cur.execute("update orderbook set status=? where id=?", [status, orderid])

cur.close()
con.commit()
con.close()



