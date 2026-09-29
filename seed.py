"""
Sample data so the app has something to show on first start:
5 vendors, 12 parts and about 45 days of sales (shop is closed on Sundays).
Names of vendors and manufacturers are made up.
"""
import math
import random
from datetime import date, timedelta

VENDORS = [
    ("Sri Balaji Auto Components", "Plot 14, Peenya Industrial Area, Bengaluru 560058", "9845012345"),
    ("Kaveri Brake Works", "22 KIADB Estate, Hosur Road, Bengaluru 560100", "9880023456"),
    ("Deccan Filters & Seals", "5/3 Balanagar Industrial Area, Hyderabad 500037", "9848034567"),
    ("Shakti Electricals", "41 SIDCO Estate, Ambattur, Chennai 600098", "9841045678"),
    ("Pune Transmission Parts", "Gat 108, Bhosari MIDC, Pune 411026", "9822056789"),
]

# part_no, name, manufacturer, make, model, rack, price, vendor_id, avg sold per day
PARTS = [
    ("BP-101", "Front Brake Pad Set", "Amar Friction Industries", "Maruti Suzuki", "Swift", "R1", 850, 2, 1.2),
    ("BP-102", "Rear Brake Shoe", "Vijay Auto Linings", "Hyundai", "i20", "R1", 620, 2, 0.6),
    ("OF-201", "Oil Filter", "Nova Filter Works", "Maruti Suzuki", "Swift", "R2", 240, 3, 2.5),
    ("AF-202", "Air Filter", "Sagar Filtration", "Honda", "Activa 6G", "R2", 180, 3, 2.0),
    ("SP-301", "Spark Plug", "Jyoti Ignition Industries", "Bajaj", "Pulsar 150", "R3", 150, 4, 3.0),
    ("HB-302", "Headlight Bulb H4", "Prakash Lamps", "Hero", "Splendor Plus", "R3", 120, 4, 1.5),
    ("BT-303", "Battery 35Ah", "Surya Batteries", "Tata", "Nexon", "R7", 5200, 4, 0.2),
    ("CP-401", "Clutch Plate", "Ganesh Clutch Works", "Royal Enfield", "Classic 350", "R4", 1450, 5, 0.4),
    ("CK-402", "Chain Sprocket Kit", "Laxmi Chains", "Bajaj", "Pulsar 150", "R4", 1100, 5, 0.7),
    ("WB-501", "Wiper Blade (pair)", "Clearview Rubber Products", "Hyundai", "i20", "R5", 450, 1, 0.9),
    ("SM-502", "Side Mirror Left", "Mehta Glass & Plastics", "Mahindra", "Bolero", "R6", 780, 1, 0.3),
    ("RH-503", "Radiator Hose", "Kumar Rubber Industries", "Tata", "Nexon", "R6", 560, 1, 0.5),
]


def load_sample_data(conn, today=None, days=45):
    today = today or date.today()
    rnd = random.Random(42)  # fixed seed -> same data every time

    conn.executemany("INSERT INTO vendors (name, address, phone) VALUES (?, ?, ?)", VENDORS)
    for p in PARTS:
        conn.execute(
            "INSERT INTO parts (part_no, name, manufacturer, vehicle_make, vehicle_model, rack_no, "
            "price, stock, vendor_id) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)", p[:8])

    # sales for the last `days` days
    sold_last_4_weeks = {p[0]: 0 for p in PARTS}
    for i in range(days, -1, -1):
        day = today - timedelta(days=i)
        if day.weekday() == 6:        # Sunday - shop closed
            continue
        for part_no, _, _, _, _, _, price, _, per_day in PARTS:
            qty = sum(1 for _ in range(6) if rnd.random() < per_day / 6)
            if qty:
                conn.execute("INSERT INTO sales (part_no, quantity, amount, sale_date) "
                             "VALUES (?, ?, ?, ?)", (part_no, qty, price * qty, day.isoformat()))
                if i < 28:
                    sold_last_4_weeks[part_no] += qty

    # current stock: most parts are fine, a few are below the threshold (need ordering)
    low = {"OF-201", "SP-301", "BP-101", "CK-402"}
    for part_no, sold in sold_last_4_weeks.items():
        limit = math.ceil(sold / 4)
        stock = rnd.randint(0, max(limit - 1, 0)) if part_no in low else limit + rnd.randint(1, 6)
        conn.execute("UPDATE parts SET stock = ? WHERE part_no = ?", (stock, part_no))
