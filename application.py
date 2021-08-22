import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute("SELECT * from hist WHERE( u = ? AND t = ?)", session["user_id"], "buy")
    
    l = []
    value = 0
    
    for row in rows:
        found = False
        value = value + row["a"] * lookup(row["s"])["price"]
        if len(l) == 0:
            l.append( {"symbol": row["s"], "amount": row["a"]} )
            continue
        for item in l:
            if row["s"]==item["symbol"]:
                item["amount"]+=row["a"]
                found = True
        if not found:    
            l.append( {"symbol": row["s"], "amount": row["a"]} )
    
    rows = db.execute("SELECT * from hist WHERE( u = ? AND t = ?)", session["user_id"], "sell")
    
    for row in rows:
        value = value - row["a"] * row["p"]
        for item in l:
            if row["s"]==item["symbol"]:
                item["amount"]-=row["a"]
    
    for item in l:
        item["name"]=lookup(item["symbol"])["name"]
        item["price"]=lookup(item["symbol"])["price"]
    for item in l:
        if item["amount"] == 0:
            l.remove(item)
        else:
            item["total"] = usd(item["amount"]*item["price"])
        item["price"]=usd(lookup(item["symbol"])["price"])
    
    cash = (db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"])
    li = [l, usd(cash), usd((value)+cash)]
    
    if len(li[0]) == 0:
        return render_template("beginner.html", li=li)
    
    return render_template("index.html", li=li)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    if request.method == "POST":
        n = request.form.get("shares")
        if not n.isnumeric():
            return apology("Please input correct amount of stock")
        n = int(n)
        if n <= 0:
            return apology("Please input correct amount of stock")
        s = request.form.get("symbol")
        if not s:
            return apology("Please input the stock symbol")
        if not lookup(s):
            return apology("The stock symbol appears to be incorrect")
        if not n:
            return apology("Please input the number of shares to be bought")
        if n <=0:
            return apology("Please input the correct number of shares to be bought")
        d = datetime.today().strftime('%Y-%m-%d')
        p = lookup(s)["price"]
        
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        
        if cash[0]["cash"] >= p * n:
            cash[0]["cash"] = cash[0]["cash"] - p*n
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash[0]["cash"], session["user_id"])
            db.execute("INSERT INTO hist(u, s, a, d, p, t) VALUES(?, ?, ?, ?, ?, ?)", session["user_id"], s, n, d, p, "buy")
        else:
            return apology("Insufficient funds")
        
        return redirect("/")
        

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT * FROM hist WHERE u = ?", session["user_id"])
    
    l = []
    
    for row in rows:
        l.append( {"name": lookup(row["s"])["name"], "symbol": row["s"], "amount": row["a"], "price": usd(row["p"]), "type": row["t"], "total": usd(row["p"]*row["a"]) } )
    for item in l:
        if item["type"] == "buy":
            item["sign"] = "-"
        else:
            item["sign"] = "+"
            
    if len(l) == 0:
        return render_template("nohistory.html")
    
    return render_template("history.html", l=l)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    
    if request.method == "GET":
        return render_template("quote.html")
    if request.method == "POST":
        result = lookup(request.form.get("symbol"))
        if result:
            result["price"]=usd(result["price"])
            return render_template("quoted.html", result = result)
    return apology("Sorry, you seem to have typed the wrong symbol")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # Handle 2 separate cases. 
    # (1) request.method=='POST' would mean that the user has provided some data
    # (2) request.method=='GET' would mean that the user has just clicked on the register button from login page
    
    if request.method == "GET":
        return render_template("register.html")
    
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        if not username:
            return apology("Please enter your username", 400)
        if not password:
            return apology("Please enter your password", 400)
        if not confirmation:
            return apology("Please enter password confirmation", 400)
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        if len(rows) > 0:
            return apology("This username is already taken")
        if not password == confirmation:
            return apology("Passwords don't match", 400)
        
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, generate_password_hash(password))
        return redirect("/")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        rows = db.execute("SELECT * from hist WHERE( u = ? AND t = ?)", session["user_id"], "buy")
        
        l = []
        value = 0
        
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
        for item in l:
            item["name"]=lookup(item["symbol"])["name"]
            item["price"]=lookup(item["symbol"])["price"]
            
        rows = db.execute("SELECT * from hist WHERE( u = ? AND t = ?)", session["user_id"], "sell")
        
        for row in rows:
            value = value - row["a"] * row["p"]
            for item in l:
                if row["s"]==item["symbol"]:
                    item["amount"]-=row["a"]
        
        for item in l:
            item["name"]=lookup(item["symbol"])["name"]
            item["price"]=lookup(item["symbol"])["price"]
        for item in l:
            if item["amount"] == 0:
                l.remove(item)
        
        if len(l) == 0:
            return render_template("nostocks.html", li=l)
            
        return render_template("sell.html", l = l)
        
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        if not symbol:
            return apology("Please select your stock symbol")
        stocks = []
        amount = 0
        
        rows = db.execute("SELECT * from hist WHERE( u = ? AND t = ?)", session["user_id"], "buy")
        
        l = []
        value = 0
        
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
        for item in l:
            item["name"]=lookup(item["symbol"])["name"]
            item["price"]=lookup(item["symbol"])["price"]
        
        for item in l:
            stocks.append(item["symbol"])
            if symbol == item["symbol"]:
                amount+=item["amount"]
        if not symbol in stocks:
            return apology("You don't seem to own this stock")
        if int(shares) > amount:
            return apology("You don't seem to have the required amount of this stock")
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        p = lookup(symbol)["price"]
        cash[0]["cash"] = cash[0]["cash"] + p*int(shares)
        d = datetime.today().strftime('%Y-%m-%d')
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash[0]["cash"], session["user_id"])
        db.execute("INSERT INTO hist(u, s, a, d, p, t) VALUES(?, ?, ?, ?, ?, ?)", session["user_id"], symbol, shares, d, p, "sell")
        
        return redirect("/")


@app.route("/pass", methods=["GET", "POST"])
@login_required
def password():
    """Change password"""
    if request.method == "GET":
        return render_template("pass.html")
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)
        if not request.form.get("new_pass1") == request.form.get("confirmation"):
            return apology("passwords don't match")
        
        db.execute("UPDATE users SET hash = ? WHERE id = ?",  generate_password_hash(request.form.get("new_pass1")), session["user_id"])
        
        return redirect("/logout")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
