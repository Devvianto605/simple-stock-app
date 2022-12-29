import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

from datetime import datetime, timezone

##import sys ## For print('', file=sys.stderr)


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

# Create new table, and index (for efficient search later on) to keep track of stock orders, by each user
db.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER, user_id NUMERIC NOT NULL, symbol TEXT NOT NULL, \
            shares NUMERIC NOT NULL, price NUMERIC NOT NULL, timestamp TEXT, PRIMARY KEY(id), \
            FOREIGN KEY(user_id) REFERENCES users(id))")


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
    stocks_owned = db.execute("SELECT symbol, SUM(shares) FROM orders WHERE user_id == ? GROUP BY symbol",session["user_id"])
    print(stocks_owned)
    investment_total = 0

    for i in range(len(stocks_owned)):
        if stocks_owned[i]['SUM(shares)'] == 0:
            del(stocks_owned[i])

    for row in stocks_owned:
        row['price'] = lookup(row['symbol'])['price']
        row['total'] = float(row['price']) * float(row['SUM(shares)'])
        print(row['price'])
        print(row['total'])

    for row in stocks_owned:
        investment_total += float(row['total'])

    investment_total = round(investment_total, 2)

    cash_total = db.execute("SELECT cash FROM users WHERE id == :id", id = session["user_id"] )
    cash = round(float(cash_total[0]['cash']), 2)
    grand_total = round(investment_total + cash, 2)

    return render_template("index.html", stocks_owned=stocks_owned,investment_total=investment_total, cash=cash, grand_total=grand_total)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        if not request.form.get("shares"):
            return apology("must provide share amount", 400)

        isnumeric = request.form.get("shares")
        if not isnumeric.isnumeric():
            return apology("Invalid number of share", 400)

        symbolinfo = lookup(request.form.get("symbol"))

        if not symbolinfo:
            return apology("Symbol not found", 400)

        if float(request.form.get("shares")) < 0:
            return apology("Invalid number of share", 400)

        symbolprice = float(symbolinfo["price"])
        shares = float(request.form.get("shares"))

        sharecheck= shares%1
        if float(sharecheck) > 0:
            return apology("Invalid number of share", 400)


        ## dbalance = db.execute("SELECT cash FROM users WHERE id == :id", id=session["user_id"])[0] ## <<< WHY [0]!!!!!!!!!
        balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"] ## <<< alternative <<< result: cash = amount of cash
        fbalance = float(balance)
        ## balancewozrar = db.execute("SELECT cash FROM users WHERE id == :id", id=session["user_id"]) ## balance without zeroth array
        ## print('balance=',balance,' balancewozrar=',balancewozrar,file=sys.stdout)
        ## output: balance= {'cash': 10000}  balancewozrar= [{'cash': 10000}]

        if (symbolprice * shares) >= fbalance:
            return apology("Insufficient fund", 403)

        fbalance = fbalance - (symbolprice * shares)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", fbalance, session["user_id"])
        db.execute("INSERT INTO orders (user_id, symbol, shares, price, timestamp) VALUES (?, ?, ?, ?, ?)", \
                                     session["user_id"], symbolinfo["symbol"], shares, symbolprice, time_now())
        ## bought = 1
        ## return redirect(url_for(".index", bought=bought)) ## <<< Try to redirect with parameter to trigger bought alert
        flash('Bought!')
        return redirect('/')

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT symbol, shares, price, timestamp FROM orders WHERE user_id = ?", session["user_id"])
    return render_template("history.html",rows=rows)


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
    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)
        symbolinfo= lookup(request.form.get("symbol"))

        if not symbolinfo:
            return apology("No symbol found.", 400)

        return render_template("quoted.html",symbolinfo=symbolinfo)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        # Forget any user_id
        session.clear()

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure confirmation was submitted and matched
        elif not request.form.get("confirmation"):
            return apology("must provide password (agian)", 400)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Password not match", 400)

        username = request.form.get("username")
        pwhash = generate_password_hash(request.form.get("password"))

         # Check wheter the username is exist
        usernamecheck = db.execute("SELECT * FROM users WHERE username = ?", username)
        if len(usernamecheck) > 0:
            return apology("username already exists", 400)
        # Then Insert new username and password into the table
        else:
            db.execute("INSERT INTO users (username,hash) VALUES (?,?)",username,pwhash)

        # Query database for username (to get id after insert is done)
        userinfo = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Remember which user has logged in
        session["user_id"] = userinfo[0]["id"]

        return redirect("/")

    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":

        sstocks_owned = db.execute("SELECT symbol, SUM(shares) FROM orders WHERE user_id == :user_id GROUP BY symbol", user_id=session["user_id"])
        stocks_dict = []

        for row in sstocks_owned:
                if row['SUM(shares)'] > 0:
                    stocks_dict.append(row['symbol'])
        print(stocks_dict)

        return render_template("sell.html",stocks_dict=stocks_dict)
    else:
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Please enter symbol", 400)
        get_quote = lookup(symbol)
        if not get_quote:
            return apology("No symbol found", 400)
        shares = request.form.get("shares")
        if not shares:
            return apology("Please enter number of share", 400)
        if float(shares) < 0:
            return apology("Invalid number of share", 400)

        current_price = get_quote["price"]
        amount_owed = current_price * float(shares)

        stocks_owned = db.execute("SELECT symbol, SUM(shares) FROM orders WHERE user_id == :user_id GROUP BY symbol", user_id=session["user_id"])
        stocks_dict = {}
        for row in stocks_owned:
            stocks_dict[row['symbol']] = row['SUM(shares)']

        shares_available = stocks_dict[symbol]
        print(shares_available)

        if float(shares) <= float(shares_available):
            balance = db.execute("SELECT cash FROM users WHERE id == :id", id=session["user_id"])[0]
            new_balance = round(balance['cash'] + amount_owed, 2)
            db.execute("UPDATE users SET cash = :cash WHERE id == :id", cash=new_balance, id=session["user_id"])
            db.execute("INSERT INTO orders (user_id, symbol, shares, price, timestamp) VALUES (?, ?, ?, ?, ?)", \
                                     session["user_id"], symbol, (-1 * float(shares)), current_price, time_now())
            flash('Sought!')
            return redirect("/")
        else:
            return apology("You are attempting to sell more shares than you own.", 400)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


#Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


#def own_shares():
#    """Helper function: Which stocks the user owns, and numbers of shares owned. Return: dictionary {symbol: qty}"""
#    owns = {}
#    query = db.execute("SELECT symbol, shares FROM orders WHERE user_id = ?", session["user_id"])
#    for q in query:
#        symbol, shares = q["symbol"], q["shares"]
#        owns[symbol] = owns.setdefault(symbol, 0) + shares
#    # filter zero-share stocks
#    owns = {k: v for k, v in owns.items() if v != 0}
#    return owns

def time_now():
    """HELPER: get current UTC date and time"""
    now_utc = datetime.now(timezone.utc)
    return str(now_utc.date()) + now_utc.time().strftime("%H:%M:%S")


## Old version of def index()
#@app.route("/")
#@login_required
#def index():
#    """Show portfolio of stocks"""
#    owns = own_shares()
#    total = 0
#    for symbol, shares in owns.items():
#        result = lookup(symbol)
#        name, price = result["name"], result["price"]
#        stock_value = shares * price
#        total += stock_value
#        owns[symbol] = (name, shares, usd(price), usd(stock_value))
#    cash = db.execute("SELECT cash FROM users WHERE id = ? ", session["user_id"])[0]['cash']
#    total += cash
#    return render_template("index.html", owns=owns, cash= usd(cash), total = usd(total))

#    ## bought = 0
#    ## if request.args['bought'] != 0:
#    ##    bought = request.args['bought'] ## <<< Try to redirect with parameter to trigger bought alert
#    ##return render_template("index.html")   #,bought=bought)
