# Motor Part Shop Software (MPSS)

A small web app for an automobile spare-parts shop. It records sales, keeps stock for every part (stored in numbered racks), works out when a part must be re-ordered (Just-In-Time idea: keep about **one week** of stock), prints the order list with the vendor's address, shows the revenue for a day, and draws a graph of sales for each day of the month.

## Tech stack

| Part | Used | Why |
|---|---|---|
| Frontend | HTML + CSS + plain JavaScript (`fetch`) | No framework to learn; 6 small pages |
| Backend | Python 3 + Flask | One file (`app.py`) holds the whole REST API |
| Database | SQLite | A single file (`mpss.db`), nothing to install |
| Graph | Plain `<div>` bars made by JavaScript | No chart library needed |
| Tests | Python `unittest` + Flask test client | Built into Python |
| Hosting | Render (free) + gunicorn | Deploys straight from GitHub |

## Run it on your computer

```bash
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000. On the first start the database is created and filled with sample data (5 vendors, 12 parts, about 45 days of sales). Delete `mpss.db` to start fresh.

## Run the tests

```bash
python -m unittest -v
```
25 tests: business logic, API input checks, and full-flow integration.

## Put it on GitHub

```bash
git init
git add .
git commit -m "Motor Part Shop Software"
git branch -M main
git remote add origin https://github.com/<your-username>/mpss.git
git push -u origin main
```

## Deploy (Render, free)

1. Sign in at https://render.com with GitHub.
2. **New → Blueprint** → pick this repository. Render reads `render.yaml`.
3. Wait for the build and open the `https://mpss-xxxx.onrender.com` link.

Note: on the free plan the disk is not permanent. When the service restarts, the database is rebuilt with fresh sample data. The free service also sleeps when unused, so the first visit can take about 30–60 seconds.

## Folder structure

```
app.py            Flask server + REST API + business logic
schema.sql        3 tables: vendors, parts, sales
seed.py           sample data
test_app.py       tests
static/           the 6 pages + style.css + common.js
diagrams/         use case, class, sequence, DFD diagrams (PNG); sources in diagrams/src
screenshots/      pictures of every page
render.yaml       deploy settings for Render
```

## Main formulas

- **Weekly average** of a part = units sold in the last 28 days ÷ 4
- **Threshold** = weekly average rounded up (≈ one week of selling)
- A part goes on the **order list** when `stock < threshold`
- **Amount required** = threshold − stock
- **Daily revenue** = sum of sale amounts on that date
- **Monthly graph** = revenue for every day of the month (0 for days with no sales)

## API

| Method | URL | Body / query | Returns |
|---|---|---|---|
| GET | `/api/vendors` | – | list of vendors |
| POST | `/api/vendors` | `{name, address, phone}` | 201 new vendor |
| GET | `/api/parts` | – | parts with `weekly_average`, `threshold`, `needs_order` |
| POST | `/api/parts` | `{part_no, name, manufacturer, vehicle_make, vehicle_model, rack_no, price, stock, vendor_id}` | 201 / 400 / 409 duplicate |
| POST | `/api/parts/<part_no>/restock` | `{quantity}` | new stock / 404 |
| GET | `/api/sales?date=YYYY-MM-DD` | date optional (today) | sales of that day |
| POST | `/api/sales` | `{part_no, quantity}` | 201 sale / 400 not enough stock / 404 |
| GET | `/api/reports/daily-revenue?date=YYYY-MM-DD` | date optional | `{date, revenue}` |
| GET | `/api/reports/order-list?date=YYYY-MM-DD` | date optional | `[{part_no, amount_required, vendor_address, ...}]` |
| GET | `/api/reports/monthly-sales?month=YYYY-MM` | month optional | one entry per day `{day, date, revenue, units}` |

All errors come back as JSON: `{"error": "message"}`.
