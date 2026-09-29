-- MPSS database: 3 tables (same as the class diagram: Vendor, Part, Sale)

DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS parts;
DROP TABLE IF EXISTS vendors;

CREATE TABLE vendors (
    vendor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    address   TEXT NOT NULL,
    phone     TEXT
);

CREATE TABLE parts (
    part_no       TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    manufacturer  TEXT,
    vehicle_make  TEXT,
    vehicle_model TEXT,
    rack_no       TEXT NOT NULL,
    price         REAL NOT NULL CHECK (price > 0),
    stock         INTEGER NOT NULL CHECK (stock >= 0),
    vendor_id     INTEGER NOT NULL REFERENCES vendors(vendor_id)
);

CREATE TABLE sales (
    sale_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    part_no   TEXT NOT NULL REFERENCES parts(part_no),
    quantity  INTEGER NOT NULL CHECK (quantity > 0),
    amount    REAL NOT NULL,
    sale_date TEXT NOT NULL            -- stored as YYYY-MM-DD
);
