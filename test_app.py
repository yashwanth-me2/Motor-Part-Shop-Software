"""
MPSS tests - run with:   python -m unittest -v
Uses Python's built-in unittest and Flask's test client (no browser, no extra installs).
Each test starts with an empty temporary database.
"""
import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta

os.environ["MPSS_DB"] = os.path.join(tempfile.gettempdir(), "mpss_test.db")
import app as mpss  # noqa: E402

TODAY = date.today()


class MPSSTestCase(unittest.TestCase):
    def setUp(self):
        mpss.init_db()                      # empty tables
        self.client = mpss.app.test_client()
        # one vendor and one part (price 100, stock 10) for most tests
        self.client.post("/api/vendors", json={"name": "Test Vendor", "address": "1 Test Road, Bengaluru"})
        self.client.post("/api/parts", json={"part_no": "P1", "name": "Brake Pad", "rack_no": "R1",
                                             "price": 100, "stock": 10, "vendor_id": 1})

    # --- helpers
    def old_sale(self, part_no, quantity, days_ago):
        """Put a sale in the past directly into the database (the API only records today's sales)."""
        conn = sqlite3.connect(mpss.app.config["DATABASE"])
        day = (TODAY - timedelta(days=days_ago)).isoformat()
        conn.execute("INSERT INTO sales (part_no, quantity, amount, sale_date) VALUES (?, ?, ?, ?)",
                     (part_no, quantity, quantity * 100, day))
        conn.commit()
        conn.close()

    def set_stock(self, part_no, stock):
        conn = sqlite3.connect(mpss.app.config["DATABASE"])
        conn.execute("UPDATE parts SET stock = ? WHERE part_no = ?", (stock, part_no))
        conn.commit()
        conn.close()

    def part(self, part_no="P1"):
        return next(p for p in self.client.get("/api/parts").get_json() if p["part_no"] == part_no)

    def order_list(self):
        return self.client.get("/api/reports/order-list?date=" + TODAY.isoformat()).get_json()


# ======================================================== backend: business logic
class TestThresholdLogic(MPSSTestCase):
    def test_weekly_average_uses_last_4_weeks_only(self):
        self.old_sale("P1", 8, days_ago=1)
        self.old_sale("P1", 4, days_ago=27)      # inside 28-day window
        self.old_sale("P1", 100, days_ago=28)    # outside window -> ignored
        self.assertEqual(self.part()["weekly_average"], 3.0)   # (8 + 4) / 4

    def test_threshold_rounds_up(self):
        self.old_sale("P1", 9, days_ago=3)       # 9 / 4 = 2.25 -> 3
        self.assertEqual(self.part()["threshold"], 3)

    def test_part_with_no_sales_is_never_ordered(self):
        self.set_stock("P1", 0)
        self.assertEqual(self.part()["threshold"], 0)
        self.assertEqual(self.order_list(), [])

    def test_stock_equal_to_threshold_is_not_ordered(self):
        self.old_sale("P1", 20, days_ago=2)      # threshold 5
        self.set_stock("P1", 5)
        self.assertEqual(self.order_list(), [])

    def test_stock_below_threshold_is_ordered_with_vendor_address(self):
        self.old_sale("P1", 20, days_ago=2)      # threshold 5
        self.set_stock("P1", 2)
        items = self.order_list()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["part_no"], "P1")
        self.assertEqual(items[0]["amount_required"], 3)          # 5 - 2
        self.assertEqual(items[0]["vendor_address"], "1 Test Road, Bengaluru")


class TestReports(MPSSTestCase):
    def test_daily_revenue_counts_only_that_day(self):
        self.old_sale("P1", 2, days_ago=0)
        self.old_sale("P1", 5, days_ago=1)
        r = self.client.get("/api/reports/daily-revenue?date=" + TODAY.isoformat()).get_json()
        self.assertEqual(r["revenue"], 200)

    def test_daily_revenue_with_no_sales_is_zero(self):
        r = self.client.get("/api/reports/daily-revenue?date=2020-01-01").get_json()
        self.assertEqual(r["revenue"], 0)

    def test_monthly_sales_has_every_day_of_month(self):
        self.assertEqual(len(self.client.get("/api/reports/monthly-sales?month=2026-09").get_json()), 30)
        self.assertEqual(len(self.client.get("/api/reports/monthly-sales?month=2026-02").get_json()), 28)
        self.assertEqual(len(self.client.get("/api/reports/monthly-sales?month=2028-02").get_json()), 29)  # leap year

    def test_monthly_sales_fills_missing_days_with_zero(self):
        self.old_sale("P1", 3, days_ago=0)
        data = self.client.get("/api/reports/monthly-sales?month=" + TODAY.strftime("%Y-%m")).get_json()
        self.assertEqual(data[TODAY.day - 1]["revenue"], 300)
        self.assertEqual(sum(d["revenue"] for d in data), 300)

    def test_bad_month_and_date_give_400(self):
        for url in ["/api/reports/monthly-sales?month=2026-13", "/api/reports/monthly-sales?month=abc",
                    "/api/reports/daily-revenue?date=29-09-2026", "/api/reports/order-list?date=hello",
                    "/api/sales?date=2026-02-30"]:
            self.assertEqual(self.client.get(url).status_code, 400, url)


# ======================================================== backend: API input checks
class TestSaleAPI(MPSSTestCase):
    def test_valid_sale_reduces_stock_and_saves_amount(self):
        r = self.client.post("/api/sales", json={"part_no": "P1", "quantity": 3})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["amount"], 300)
        self.assertEqual(self.part()["stock"], 7)
        self.assertEqual(len(self.client.get("/api/sales").get_json()), 1)

    def test_bad_quantities_are_rejected(self):
        for q in [0, -2, 2.5, "3", True, None]:
            r = self.client.post("/api/sales", json={"part_no": "P1", "quantity": q})
            self.assertEqual(r.status_code, 400, q)
        self.assertEqual(self.part()["stock"], 10)          # nothing changed

    def test_selling_more_than_stock_is_rejected(self):
        r = self.client.post("/api/sales", json={"part_no": "P1", "quantity": 11})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Not enough stock", r.get_json()["error"])
        self.assertEqual(self.part()["stock"], 10)
        self.assertEqual(self.client.get("/api/sales").get_json(), [])

    def test_selling_exact_stock_leaves_zero(self):
        self.client.post("/api/sales", json={"part_no": "P1", "quantity": 10})
        self.assertEqual(self.part()["stock"], 0)

    def test_unknown_part_gives_404(self):
        r = self.client.post("/api/sales", json={"part_no": "NOPE", "quantity": 1})
        self.assertEqual(r.status_code, 404)

    def test_lowercase_part_number_works(self):
        r = self.client.post("/api/sales", json={"part_no": " p1 ", "quantity": 1})
        self.assertEqual(r.status_code, 201)

    def test_empty_or_non_json_body_gives_400_not_crash(self):
        self.assertEqual(self.client.post("/api/sales").status_code, 400)
        self.assertEqual(self.client.post("/api/sales", data="hello").status_code, 400)


class TestPartAndVendorAPI(MPSSTestCase):
    def test_duplicate_part_number_gives_409(self):
        r = self.client.post("/api/parts", json={"part_no": "p1", "name": "X", "rack_no": "R2",
                                                 "price": 50, "vendor_id": 1})
        self.assertEqual(r.status_code, 409)

    def test_part_input_checks(self):
        good = {"part_no": "P2", "name": "Filter", "rack_no": "R2", "price": 50, "stock": 0, "vendor_id": 1}
        bad_cases = [dict(good, price=0), dict(good, price=-5), dict(good, price="50"),
                     dict(good, stock=-1), dict(good, stock=1.5), dict(good, vendor_id=99),
                     dict(good, name=""), dict(good, rack_no="  ")]
        for case in bad_cases:
            self.assertEqual(self.client.post("/api/parts", json=case).status_code, 400, case)
        self.assertEqual(self.client.post("/api/parts", json=good).status_code, 201)

    def test_vendor_needs_name_and_address(self):
        self.assertEqual(self.client.post("/api/vendors", json={"name": "A"}).status_code, 400)
        self.assertEqual(self.client.post("/api/vendors", json={"name": "A", "address": "B"}).status_code, 201)

    def test_restock(self):
        self.assertEqual(self.client.post("/api/parts/P1/restock", json={"quantity": 5}).get_json()["stock"], 15)
        self.assertEqual(self.client.post("/api/parts/P1/restock", json={"quantity": 0}).status_code, 400)
        self.assertEqual(self.client.post("/api/parts/NOPE/restock", json={"quantity": 5}).status_code, 404)

    def test_html_in_names_is_stored_as_plain_text(self):
        self.client.post("/api/vendors", json={"name": "<script>x</script>", "address": "A"})
        names = [v["name"] for v in self.client.get("/api/vendors").get_json()]
        self.assertIn("<script>x</script>", names)   # frontend shows it with esc(), never runs it


# ======================================================== integration: whole flow
class TestIntegration(MPSSTestCase):
    def test_full_day_flow(self):
        # history: 40 sold in last 4 weeks -> threshold 10. Stock is 10 -> OK for now
        self.old_sale("P1", 40, days_ago=5)
        self.assertEqual(self.order_list(), [])
        # sell 4 today through the API -> stock 6 < 10 -> must be ordered
        self.client.post("/api/sales", json={"part_no": "P1", "quantity": 4})
        items = self.order_list()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["threshold"], 11)          # today's 4 sales also count: 44 / 4
        self.assertEqual(items[0]["amount_required"], 5)     # 11 - 6
        self.assertTrue(self.part()["needs_order"])
        # today's revenue = 4 x 100
        rev = self.client.get("/api/reports/daily-revenue").get_json()["revenue"]
        self.assertEqual(rev, 400)
        # vendor delivers -> restock -> no longer on the list
        self.client.post("/api/parts/P1/restock", json={"quantity": 5})
        self.assertEqual(self.order_list(), [])

    def test_pages_and_unknown_routes(self):
        for page in ["/", "/parts.html", "/vendors.html", "/sale.html", "/order.html", "/reports.html"]:
            with self.client.get(page) as r:
                self.assertEqual(r.status_code, 200, page)
        r = self.client.get("/api/does-not-exist")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.get_json()["error"], "Not found")   # JSON, so the frontend can show it

    def test_sample_data_loads(self):
        mpss.init_db(with_sample_data=True)
        self.assertEqual(len(self.client.get("/api/vendors").get_json()), 5)
        self.assertEqual(len(self.client.get("/api/parts").get_json()), 12)
        self.assertGreater(len(self.order_list()), 0)


if __name__ == "__main__":
    unittest.main()
