from cs50 import SQL
from helpers import apology, login_required, lookup, usd

db = SQL("sqlite:///finance.db")
rows = db.execute("SELECT * from trnsct WHERE u = ?", 1)
l = []
value = 0
print(len(l) == 0)

for row in rows:
    value += row["a"] * lookup(row["s"])["price"]
    if len(l) == 0:
        l.append( {"symbol": row["s"], "amount": row["a"]} )
        continue
    for item in l:
        if row["s"]==item["symbol"]:
            item["amount"]+=row["a"]
        else:
            l.append( {"symbol": row["s"], "amount": row["a"]} )

print(l)
print(value)