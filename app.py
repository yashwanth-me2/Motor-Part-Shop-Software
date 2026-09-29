"""
Motor Part Shop Software (MPSS) - backend
Flask (web server + REST API) and SQLite (database file).

The code is grouped the same way as the class diagram:
    Vendor  -> /api/vendors
    Part    -> weekly_average(), threshold(), amount_required(), restock()
    Sale    -> record_sale()
    ReportGenerator -> daily_revenue(), order_list(), monthly_sales()
"""
import calendar
import math
import os
import sqlite3
from datetime import date, timedelta

from flask import Flask, g, jsonify, request

import seed

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["DATABASE"] = os.environ.get("MPSS_DB", "mpss.db")

WEEKS_TO_AVERAGE = 4  # weekly average = sales of the last 4 weeks / 4


# ---------------------------------------------------------------- database
def db():
    """Open one database connection per request."""
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row          # rows behave like dicts
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(error):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db(with_sample_data=False):
    """Create empty tables (and optionally load sample data)."""
    conn = sqlite3.connect(app.config["DATABASE"])
    with open(os.path.join(os.path.dirname(__file__), "schema.sql")) as f:
        conn.executescript(f.read())
    if with_sample_data:
        seed.load_sample_data(conn)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- helpers
def error(message, status=400):
    return jsonify({"error": message}), status


def positive_int(value):
    """Return value if it is a whole number > 0, else None."""
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def read_date(text):
    """'2026-09-29' -> date. Missing -> today. Wrong format -> None."""
    if not text:
        return date.today()
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


# ---------------------------------------------------------------- Part logic
def weekly_average(part_no, day):
    """Average units sold per week, using the 4 weeks (28 days) ending on `day`."""
    start = day - timedelta(days=WEEKS_TO_AVERAGE * 7 - 1)
    sold = db().execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM sales "
        "WHERE part_no = ? AND sale_date BETWEEN ? AND ?",
        (part_no, start.isoformat(), day.isoformat()),
    ).fetchone()[0]
    return sold / WEEKS_TO_AVERAGE


def threshold(part_no, day):
    """Stock needed to sell for about one week (JIT) = weekly average, rounded up."""
    return math.ceil(weekly_average(part_no, day))


def amount_required(part, day):
    """How many to order: fill stock back up to the threshold."""
    limit = threshold(part["part_no"], day)
    return limit - part["stock"] if part["stock"] < limit else 0


def restock(part_no, quantity):
    cur = db().execute("UPDATE parts SET stock = stock + ? WHERE part_no = ?", (quantity, part_no))
    db().commit()
    return cur.rowcount == 1


# ---------------------------------------------------------------- Sale logic
def record_sale(part_no, quantity):
    """Save a sale and reduce stock. Returns (sale, error_message)."""
    part = db().execute("SELECT * FROM parts WHERE part_no = ?", (part_no,)).fetchone()
    if part is None:
        return None, "Part not found"
    # reduce stock only if enough is left (checked inside the same UPDATE)
    cur = db().execute(
        "UPDATE parts SET stock = stock - ? WHERE part_no = ? AND stock >= ?",
        (quantity, part_no, quantity),
    )
    if cur.rowcount == 0:
        return None, f"Not enough stock (only {part['stock']} left)"
    amount = round(part["price"] * quantity, 2)
    today = date.today().isoformat()
    cur = db().execute(
        "INSERT INTO sales (part_no, quantity, amount, sale_date) VALUES (?, ?, ?, ?)",
        (part_no, quantity, amount, today),
    )
    db().commit()
    return {"sale_id": cur.lastrowid, "part_no": part_no, "quantity": quantity,
            "amount": amount, "sale_date": today}, None


# ---------------------------------------------------------------- ReportGenerator logic
def daily_revenue(day):
    return db().execute(
        "SELECT COALESCE(SUM(amount), 0) FROM sales WHERE sale_date = ?", (day.isoformat(),)
    ).fetchone()[0]


def order_list(day):
    """Parts whose stock is below the threshold: part no., amount required, vendor address."""
    parts = db().execute(
        "SELECT p.*, v.name AS vendor_name, v.address AS vendor_address "
        "FROM parts p JOIN vendors v ON v.vendor_id = p.vendor_id ORDER BY p.part_no"
    ).fetchall()
    items = []
    for part in parts:
        amount = amount_required(part, day)
        if amount > 0:
            items.append({"part_no": part["part_no"], "name": part["name"],
                          "stock": part["stock"], "threshold": threshold(part["part_no"], day),
                          "amount_required": amount, "vendor_name": part["vendor_name"],
                          "vendor_address": part["vendor_address"]})
    return items


def monthly_sales(year, month):
    """Revenue for every day of the month (days with no sales get 0)."""
    rows = db().execute(
        "SELECT sale_date, SUM(amount) AS revenue, SUM(quantity) AS units FROM sales "
        "WHERE sale_date LIKE ? GROUP BY sale_date",
        (f"{year:04d}-{month:02d}-%",),
    ).fetchall()
    found = {r["sale_date"]: r for r in rows}
    days_in_month = calendar.monthrange(year, month)[1]
    result = []
    for d in range(1, days_in_month + 1):
        key = f"{year:04d}-{month:02d}-{d:02d}"
        row = found.get(key)
        result.append({"day": d, "date": key,
                       "revenue": round(row["revenue"], 2) if row else 0,
                       "units": row["units"] if row else 0})
    return result


# ================================================================ API routes
@app.route("/")
def home():
    return app.send_static_file("index.html")


# ----- vendors
@app.get("/api/vendors")
def get_vendors():
    rows = db().execute("SELECT * FROM vendors ORDER BY vendor_id").fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/vendors")
def add_vendor():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    address = str(data.get("address", "")).strip()
    phone = str(data.get("phone", "")).strip()
    if not name or not address:
        return error("Name and address are required")
    cur = db().execute("INSERT INTO vendors (name, address, phone) VALUES (?, ?, ?)",
                       (name, address, phone))
    db().commit()
    return jsonify({"vendor_id": cur.lastrowid, "name": name, "address": address, "phone": phone}), 201


# ----- parts
@app.get("/api/parts")
def get_parts():
    today = date.today()
    rows = db().execute(
        "SELECT p.*, v.name AS vendor_name FROM parts p "
        "JOIN vendors v ON v.vendor_id = p.vendor_id ORDER BY p.rack_no, p.part_no"
    ).fetchall()
    result = []
    for r in rows:
        part = dict(r)
        part["weekly_average"] = weekly_average(r["part_no"], today)
        part["threshold"] = threshold(r["part_no"], today)
        part["needs_order"] = amount_required(r, today) > 0
        result.append(part)
    return jsonify(result)


@app.post("/api/parts")
def add_part():
    data = request.get_json(silent=True) or {}
    part_no = str(data.get("part_no", "")).strip().upper()
    name = str(data.get("name", "")).strip()
    rack_no = str(data.get("rack_no", "")).strip()
    price = data.get("price")
    stock = data.get("stock", 0)
    vendor_id = data.get("vendor_id")

    if not part_no or not name or not rack_no:
        return error("Part number, name and rack number are required")
    if not isinstance(price, (int, float)) or isinstance(price, bool) or price <= 0:
        return error("Price must be a number greater than 0")
    if stock != 0 and positive_int(stock) is None:
        return error("Stock must be a whole number, 0 or more")
    if db().execute("SELECT 1 FROM vendors WHERE vendor_id = ?", (vendor_id,)).fetchone() is None:
        return error("Vendor not found")
    if db().execute("SELECT 1 FROM parts WHERE part_no = ?", (part_no,)).fetchone():
        return error("Part number already exists", 409)

    db().execute(
        "INSERT INTO parts (part_no, name, manufacturer, vehicle_make, vehicle_model, rack_no, "
        "price, stock, vendor_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (part_no, name, str(data.get("manufacturer", "")).strip(),
         str(data.get("vehicle_make", "")).strip(), str(data.get("vehicle_model", "")).strip(),
         rack_no, price, stock, vendor_id),
    )
    db().commit()
    return jsonify({"part_no": part_no, "message": "Part added"}), 201


@app.post("/api/parts/<part_no>/restock")
def restock_part(part_no):
    data = request.get_json(silent=True) or {}
    quantity = positive_int(data.get("quantity"))
    if quantity is None:
        return error("Quantity must be a whole number greater than 0")
    if not restock(part_no, quantity):
        return error("Part not found", 404)
    stock = db().execute("SELECT stock FROM parts WHERE part_no = ?", (part_no,)).fetchone()[0]
    return jsonify({"part_no": part_no, "stock": stock})


# ----- sales
@app.get("/api/sales")
def get_sales():
    day = read_date(request.args.get("date"))
    if day is None:
        return error("Date must be YYYY-MM-DD")
    rows = db().execute(
        "SELECT s.*, p.name FROM sales s JOIN parts p ON p.part_no = s.part_no "
        "WHERE s.sale_date = ? ORDER BY s.sale_id DESC", (day.isoformat(),)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/sales")
def add_sale():
    data = request.get_json(silent=True) or {}
    part_no = str(data.get("part_no", "")).strip().upper()
    quantity = positive_int(data.get("quantity"))
    if not part_no:
        return error("Part number is required")
    if quantity is None:
        return error("Quantity must be a whole number greater than 0")
    sale, message = record_sale(part_no, quantity)
    if message == "Part not found":
        return error(message, 404)
    if message:
        return error(message)
    return jsonify(sale), 201


# ----- reports
@app.get("/api/reports/daily-revenue")
def get_daily_revenue():
    day = read_date(request.args.get("date"))
    if day is None:
        return error("Date must be YYYY-MM-DD")
    return jsonify({"date": day.isoformat(), "revenue": round(daily_revenue(day), 2)})


@app.get("/api/reports/order-list")
def get_order_list():
    day = read_date(request.args.get("date"))
    if day is None:
        return error("Date must be YYYY-MM-DD")
    return jsonify(order_list(day))


@app.get("/api/reports/monthly-sales")
def get_monthly_sales():
    text = request.args.get("month") or date.today().strftime("%Y-%m")
    try:
        year, month = (int(x) for x in text.split("-"))
        if not 1 <= month <= 12:
            raise ValueError
    except ValueError:
        return error("Month must be YYYY-MM")
    return jsonify(monthly_sales(year, month))


@app.errorhandler(404)
def not_found(e):
    return error("Not found", 404)


# First start: create the database and fill it with sample data
if not os.path.exists(app.config["DATABASE"]):
    init_db(with_sample_data=True)

if __name__ == "__main__":
    app.run(debug=True)
