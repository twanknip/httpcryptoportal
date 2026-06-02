#! /usr/bin/python3

#
# sqlite program for creating the cryptoportal database
#

import sqlite3

con = sqlite3.connect("cryptoportal.db")
cur = con.cursor()

cur.execute("DROP TABLE IF EXISTS wallet")
cur.execute("CREATE TABLE wallet(id, hash)")
cur.execute("INSERT INTO wallet VALUES( 314, '642606e93992a316419e8b6081af73dd')")
cur.execute("INSERT INTO wallet VALUES( 159, '78085aa67eaa6d90ad7b067e5a05cd5e')")
cur.execute("INSERT INTO wallet VALUES( 265, '259a568c9e5262afa3bb020a24f9457e')")
cur.execute("INSERT INTO wallet VALUES( 358, '173bb7ab566b5ff777d6f6bc8cfd0e63')")

for row in cur.execute("SELECT * FROM wallet"):
    print(row)
    
cur.execute("DROP TABLE IF EXISTS crypto")
cur.execute("CREATE TABLE crypto(id, name)")
cur.execute("INSERT INTO crypto VALUES( 1, 'Bitcoin (BTC)')")
cur.execute("INSERT INTO crypto VALUES( 2, 'Ethereum (ETH)')")
cur.execute("INSERT INTO crypto VALUES( 3, 'Tether (USDT)')")
cur.execute("INSERT INTO crypto VALUES( 4, 'USD Coin (USDC)')")

for row in cur.execute("SELECT * FROM crypto"):
    print(row)
    
cur.execute("DROP TABLE IF EXISTS orderbook")
cur.execute("CREATE TABLE orderbook(id, walletid, cryptoid, side, price, currency, qty, status)")
cur.execute("INSERT INTO orderbook VALUES( 1, 314, 1, 'Buy' , 89535, 'EUR',     2, 'NEW')")
cur.execute("INSERT INTO orderbook VALUES( 2, 314, 1, 'Sell', 89546, 'EUR',     2, 'NEW')")
cur.execute("INSERT INTO orderbook VALUES( 3, 314, 2, 'Buy' ,  3270, 'EUR',    17, 'NEW')")
cur.execute("INSERT INTO orderbook VALUES( 4, 159, 2, 'Buy' ,  3269, 'EUR',    27, 'NEW')")
cur.execute("INSERT INTO orderbook VALUES( 5, 159, 3, 'Buy' ,     1, 'USD', 20000, 'NEW')")
cur.execute("INSERT INTO orderbook VALUES( 6, 159, 3, 'Sell',     2, 'USD', 12000, 'NEW')")
cur.execute("INSERT INTO orderbook VALUES( 7, 265, 1, 'Buy' , 74403, 'GBP',     2, 'NEW')")
cur.execute("INSERT INTO orderbook VALUES( 8, 265, 1, 'Sell', 74567, 'GBP',     6, 'NEW')")
cur.execute("INSERT INTO orderbook VALUES( 9, 265, 1, 'Sell', 73987, 'GBP',     5, 'NEW')")
cur.execute("INSERT INTO orderbook VALUES(10, 358, 4, 'Buy' ,     7, 'USD', 30000, 'NEW')")
cur.execute("INSERT INTO orderbook VALUES(11, 358, 4, 'Sell',     6, 'USD', 25000, 'NEW')")
cur.execute("INSERT INTO orderbook VALUES(12, 358, 4, 'Buy' ,     6, 'USD', 10000, 'NEW')")

for row in cur.execute("SELECT * FROM orderbook"):
    print(row)

cur.close()
con.commit()
con.close()
