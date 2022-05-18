import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    #Deleting indices where number of shares is zero
    db.execute("DELETE FROM shares WHERE no_shares = 0")

    symbols = db.execute("SELECT DISTINCT(symbol) FROM shares WHERE user_id = ?", session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

    #will count total assests of the user
    total = 0

    # Will store all the data about each symbol
    dict = [{}] * len(symbols)

    for i in range(len(symbols)):

        dict[i] = db.execute("SELECT symbol,name,SUM(no_shares) FROM shares WHERE symbol = ? AND user_id = ?", symbols[i]["symbol"], session["user_id"])
        data  = lookup(symbols[i]['symbol'])
        dict[i].append({
            "price" : data["price"]
        })
        dict[i].append({
            "total" : data["price"] * dict[i][0]['SUM(no_shares)']
        })

    for i in dict:
        total += i[2]['total']

    total += cash[0]['cash']
    #print(dict)

    return render_template("index.html",dict=dict,cash=cash[0]['cash'],total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # if requested via POST
    if request.method == "POST":
        # Getting the form elements
        symbol = request.form.get('symbol')
        shares = request.form.get('shares')

        #Checking if the shares contains digits only
        if not shares.isdigit():
            return apology("Invalid Number of shares",400)

        # Validating rest of input
        if symbol is None:
            return apology("missing symbol", 400)
        elif shares is None:
            return apology("missing shares", 400)
        elif int(shares) < 1:
            return apology("Number of shares to buy can't be negative", 400)

        #validation of symbol
        check_symbol = lookup(symbol)

        if check_symbol is None:
            return apology("Invalid Symbol", 400)

       # Checking for the user's cash and decrementing it on the basis of pusrchased shares
        users_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])

        cash_required = check_symbol["price"] * int(shares)

        users_cash[0]['cash'] = users_cash[0]['cash'] - cash_required

        if users_cash[0]['cash'] < 0:
            return apology("Not Enough cash",400)

        #inserting data
        db.execute("UPDATE users SET cash = ? WHERE id = ?", users_cash[0]['cash'], session["user_id"])
        db.execute("INSERT INTO shares(user_id,no_shares,symbol,price_per_share,name) VALUES(?,?,?,?,?)",session["user_id"], shares, symbol, usd(check_symbol["price"]), check_symbol["name"])

        #updating history
        db.execute("INSERT INTO history(user_id,symbol,shares,price,dt) VALUES(?,?,?,?,datetime('now'))", session["user_id"], symbol, shares, check_symbol["price"])

        return redirect("/")

    #if requested via GET
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    data = db.execute("SELECT * FROM history WHERE user_id = ? ORDER BY dt", session["user_id"])
    return render_template("history.html",data=data)


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

    # if method is POST
    if request.method == "POST":
       # getting symbol
       symbol = request.form.get('symbol')

       # fetching lookout for symbol
       data = lookup(symbol)

       # Checking id the data exists
       if data is None:
             return apology("INVALID SYMBOL",400)

       return render_template("quoted.html",data=data)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget Any User Id
    session.clear()

    # If accesed through post method (Submited the Register Froum)
    if request.method == "POST":

        # accesing the forms input
         name = request.form.get('username')
         password = request.form.get('password')
         repassword = request.form.get('confirmation')


        # checks for valid name and passwords
         if not name or name == " " or not password or not repassword:
             return apology("must provide username/password",400)
         elif password != repassword:
             return apology("Password don't match",400)

         # check if the username already exits
         rows = db.execute("SELECT * FROM users WHERE username = ?", name)

         if len(rows) != 0:
             return apology("Username already exits",400)

         # insert user data
         db.execute("INSERT INTO users(username,hash) VALUES(?,?)",name,generate_password_hash(password))

         rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
         session["user_id"] = rows[0]["id"]

         return redirect("/")
    # accesed through GET directly to the page
    else:
        return  render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    #Route via POST
    if request.method == "POST":
        #Fetching user input
        symbol = request.form.get('symbol')
        shares = request.form.get('shares')

        # Validating Shares and Symbols
        if not shares.isdigit() or int(shares) < 1:
            return apology("Invalid Shares",400)
        if symbol is None:
            return apology("MISSING SYMBOL",400)

        #Total shares user has
        no_shares = db.execute("SELECT SUM(no_shares) FROM shares WHERE user_id = ? AND symbol = ?", session["user_id"],
        symbol)

        if no_shares[0]["SUM(no_shares)"] < int(shares):
            return apology("TOO MANY SHARES",400)


        shares = int(shares)

        # Calculating money got by selling shares and updating it in users table
        price = lookup(symbol)
        profit = price["price"] * shares
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        total_cash = profit + cash[0]['cash']
        db.execute("UPDATE users SET cash = ? WHERE id = ?", total_cash, session["user_id"])

        #Fetching list of all the shares and Deleting shares from the database
        list_shares = db.execute("SELECT no_shares,id FROM shares WHERE user_id = ? AND symbol = ? ORDER BY no_shares DESC" , session["user_id"], symbol)

        for share in list_shares:
            if shares > share['no_shares']:
                shares -= share['no_shares']
                db.execute("DELETE FROM shares WHERE id = ?", share['id'])
            else:
                share['no_shares'] -= shares
                db.execute("UPDATE shares SET no_shares = ? WHERE id = ?", share['no_shares'], share['id'])
                break


        #updating history
        db.execute("INSERT INTO history(user_id,symbol,shares,price,dt) VALUES(?,?,?,?,datetime('now'))", session["user_id"], symbol, shares*-1, price["price"])

        return redirect("/")

    #Route via GET
    else:
        #Fetching the list of symbols for shares user bought
        symbols = db.execute("SELECT DISTINCT(symbol) FROM shares WHERE user_id = ?", session["user_id"])
        #print(symbols)
        return render_template("sell.html",symbols=symbols)


@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def add_cash():
    """Add's Cash"""

    if request.method == "POST":
          money = request.form.get('cash')

          if not money.isdigit():
              return apology("INVALID AMOUNT",400)

          money = int(money)

          if money < 500:
              return apology("AMOUNT TOO LOW",400)

          cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
          money += cash[0]['cash']
          db.execute("UPDATE users SET cash = ? WHERE id = ?", money, session["user_id"])

          return redirect("/")
    else:
        return render_template("add_cash.html")
   


