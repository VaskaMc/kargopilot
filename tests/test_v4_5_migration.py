"""Verification test suite for KargoPilot v4.5 non-destructive multi-tenant migration."""

import sqlite3
import time
from pathlib import Path
import pytest

def test_v4_5_non_destructive_migration(tmp_path: Path):
    test_db = tmp_path / "pcs_test.db"

    conn = sqlite3.connect(str(test_db))
    cur = conn.cursor()

    # 1. Create v4.0 baseline schema
    cur.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE orders (
        id TEXT PRIMARY KEY,
        platform TEXT DEFAULT 'Temu',
        temu_order_ref TEXT UNIQUE,
        tracking_number TEXT,
        carrier TEXT,
        receiver_name TEXT,
        receiver_phone TEXT,
        original_amount REAL,
        original_currency TEXT DEFAULT 'AZN',
        fx_rate_to_azn REAL DEFAULT 1.0,
        fx_rate_to_usd REAL DEFAULT 0.5882,
        invoice_amount_azn REAL,
        invoice_amount_usd REAL,
        temu_invoice_amount REAL,
        temu_invoice_currency TEXT DEFAULT 'AZN',
        status TEXT DEFAULT 'STORED',
        extra TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fin TEXT DEFAULT '6N89P92'
    );

    CREATE TABLE order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT,
        title TEXT NOT NULL,
        main_cat TEXT NOT NULL,
        sub_cat TEXT DEFAULT 'Digər',
        quantity INTEGER DEFAULT 1,
        unit_price REAL DEFAULT 0.0,
        retail_price REAL DEFAULT 0.0,
        price_unknown BOOLEAN DEFAULT 0,
        total_price REAL DEFAULT 0.0,
        adjusted_price REAL,
        currency TEXT DEFAULT 'AZN',
        unit_price_azn REAL,
        total_price_azn REAL,
        total_price_usd REAL,
        extra TEXT,
        FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
    );

    CREATE TABLE customs_declarations (
        id TEXT PRIMARY KEY,
        order_id TEXT,
        customs_ref TEXT,
        status TEXT DEFAULT 'Bəyan edilib',
        payload TEXT,
        screenshot_path TEXT,
        duty_estimate_azn REAL DEFAULT 0.0,
        sum_adjusted REAL,
        submitted_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE SET NULL
    );

    CREATE TABLE fin_profiles (
        fin TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        phone TEXT,
        is_active INTEGER DEFAULT 0,
        monthly_limit_usd REAL DEFAULT 300.0,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE carrier_accounts (
        id VARCHAR(40) PRIMARY KEY,
        carrier_name VARCHAR(32) NOT NULL,
        customer_code VARCHAR(32) NOT NULL,
        email VARCHAR(120),
        auth_token TEXT,
        is_active BOOLEAN DEFAULT 1,
        default_branch VARCHAR(64) DEFAULT '28 May',
        warehouse_suites JSON,
        last_sync_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed 10 orders, 78 items, 4 customs declarations, 1 carrier account, 2 fin profiles
    for i in range(10):
        order_id = f"ord-v4-{i+1:03d}"
        cur.execute("""
            INSERT INTO orders (id, temu_order_ref, tracking_number, carrier, receiver_name, receiver_phone, invoice_amount_azn, invoice_amount_usd, status)
            VALUES (?, ?, ?, 'STAREX', 'Vasif Məcidli', '+994776346310', 50.0, 29.41, 'SUBMITTED')
        """, (order_id, f"PO-V4-{i+1:04d}", f"TRK-{i+1:05d}"))
        
        items_for_this_order = 8 if i < 8 else 7
        for j in range(items_for_this_order):
            cur.execute("""
                INSERT INTO order_items (order_id, title, main_cat, sub_cat, quantity, unit_price, total_price)
                VALUES (?, ?, 'Geyim aksesuarları', 'Digər', 1, 6.25, 6.25)
            """, (order_id, f"Item {i+1}-{j+1}"))

        if i < 4:
            cur.execute("""
                INSERT INTO customs_declarations (id, order_id, customs_ref, status)
                VALUES (?, ?, ?, 'Bəyan edilib')
            """, (f"decl-v4-{i+1:03d}", order_id, f"6209481{i}"))

    cur.execute("""
        INSERT INTO fin_profiles (fin, full_name, phone, is_active, monthly_limit_usd, notes)
        VALUES ('6N89P92', 'Vasif Məcidli', '+994776346310', 1, 300.0, 'Legacy profile'),
               ('5K99A12', 'Ailə Üzvü', '+994776346310', 0, 300.0, 'Secondary profile')
    """)

    cur.execute("""
        INSERT INTO carrier_accounts (id, carrier_name, customer_code, default_branch, auth_token)
        VALUES ('acc-001', 'STAREX', 'SX-9921', '28 May', 'ey...')
    """)

    conn.commit()

    # Pre-migration verification
    assert cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 10
    assert cur.execute("SELECT COUNT(*) FROM order_items").fetchone()[0] == 78
    assert cur.execute("SELECT COUNT(*) FROM customs_declarations").fetchone()[0] == 4

    # 2. Run the migration script
    migration_file = Path(__file__).resolve().parent.parent / "web_panel" / "app" / "db" / "migrations" / "v4_0_to_v4_5_multitenant.sql"
    migration_sql = migration_file.read_text(encoding="utf-8")
    cur.executescript(migration_sql)
    conn.commit()

    # 3. Post-migration verification
    superadmin_id = "00000000-0000-4000-8000-000000000001"
    
    # Verify Superadmin
    admin = cur.execute("SELECT * FROM users WHERE id = ?", (superadmin_id,)).fetchone()
    assert admin is not None
    assert admin[1] == "vasif@kargopilot.az"
    assert admin[3] == "Vasif Məcidli"
    assert admin[4] == "+994776346310"
    assert admin[5] == "superadmin"

    # Verify orders scoped to superadmin
    orders_count = cur.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (superadmin_id,)).fetchone()[0]
    orphaned_orders = cur.execute("SELECT COUNT(*) FROM orders WHERE user_id IS NULL").fetchone()[0]
    assert orders_count == 10
    assert orphaned_orders == 0

    # Verify items
    items_count = cur.execute("SELECT COUNT(*) FROM order_items").fetchone()[0]
    assert items_count == 78

    # Verify customs declarations
    decl_count = cur.execute("SELECT COUNT(*) FROM customs_declarations WHERE user_id = ?", (superadmin_id,)).fetchone()[0]
    assert decl_count == 4

    # Verify FIN profiles
    primary_fin = cur.execute("SELECT fin, full_name, is_primary FROM fin_profiles WHERE user_id = ? AND is_primary = 1", (superadmin_id,)).fetchone()
    assert primary_fin[0] == "814CRM4"
    assert primary_fin[1] == "Vasif Məcidli"

    # Verify Audit log
    audit = cur.execute("SELECT action, resource, details_json FROM audit_logs WHERE user_id = ?", (superadmin_id,)).fetchone()
    assert audit is not None

    # Benchmark query speed
    t0 = time.perf_counter()
    cur.execute("""
        SELECT o.*, cd.customs_ref, COUNT(oi.id) as item_count
        FROM orders o
        LEFT JOIN customs_declarations cd ON cd.order_id = o.id
        LEFT JOIN order_items oi ON oi.order_id = o.id
        WHERE o.user_id = ?
        GROUP BY o.id
        ORDER BY o.created_at DESC
    """, (superadmin_id,)).fetchall()
    t1 = time.perf_counter()
    query_time_ms = (t1 - t0) * 1000
    assert query_time_ms < 20.0

    conn.close()
