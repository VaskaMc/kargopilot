"""Database layer for PCS Web Panel supporting the complete PCS database schema."""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import (
    DB_PATH,
    CONSIGNEE_NAME,
    CONSIGNEE_PHONE,
    USD_AZN_RATE,
)

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """Returns an active SQLite connection with row factory enabled."""
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    """Initializes tables adhering to the production PCS schema and ensures seed records."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
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
        last_sync_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
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
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS customs_declarations (
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
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS platform_sessions (
        platform TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        auth_type TEXT,
        username_hint TEXT,
        last_authenticated_at TIMESTAMP,
        expires_at TIMESTAMP,
        details TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS fin_profiles (
        fin TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        phone TEXT,
        is_active INTEGER DEFAULT 0,
        monthly_limit_usd REAL DEFAULT 300.0,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS product_category_cache (
        title_hash TEXT PRIMARY KEY,
        raw_title TEXT NOT NULL,
        main_cat TEXT NOT NULL,
        sub_cat TEXT DEFAULT 'Digər',
        confidence REAL DEFAULT 1.0,
        source TEXT DEFAULT 'deterministic',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Ensure all required columns exist in orders table
    order_cols = [r[1] for r in cur.execute("PRAGMA table_info(orders)").fetchall()]
    if "platform" not in order_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN platform TEXT DEFAULT 'Temu'")
    if "fin" not in order_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN fin TEXT DEFAULT '814CRM4'")
    if "original_amount" not in order_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN original_amount REAL")
    if "original_currency" not in order_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN original_currency TEXT DEFAULT 'AZN'")
    if "fx_rate_to_azn" not in order_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN fx_rate_to_azn REAL DEFAULT 1.0")
    if "fx_rate_to_usd" not in order_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN fx_rate_to_usd REAL DEFAULT 0.5882")
    if "invoice_amount_usd" not in order_cols:
        cur.execute("ALTER TABLE orders ADD COLUMN invoice_amount_usd REAL")

    # Ensure all required columns exist in order_items table
    item_cols = [r[1] for r in cur.execute("PRAGMA table_info(order_items)").fetchall()]
    if "currency" not in item_cols:
        cur.execute("ALTER TABLE order_items ADD COLUMN currency TEXT DEFAULT 'AZN'")
    if "unit_price_azn" not in item_cols:
        cur.execute("ALTER TABLE order_items ADD COLUMN unit_price_azn REAL")
    if "total_price_azn" not in item_cols:
        cur.execute("ALTER TABLE order_items ADD COLUMN total_price_azn REAL")
    if "total_price_usd" not in item_cols:
        cur.execute("ALTER TABLE order_items ADD COLUMN total_price_usd REAL")

    # Check if we have order_items populated. If 0 items, seed the production orders with items
    items_count = cur.execute("SELECT COUNT(*) FROM order_items").fetchone()[0]
    if items_count == 0:
        logger.info("Populating rich PCS production orders with full item catalog...")
        _seed_data(conn)

    # Ensure platform sessions, fin profiles, and multi-tenant auth tables exist
    _ensure_platform_sessions(conn)
    _ensure_fin_profiles(conn)
    _ensure_users_and_auth_tables(conn)

    conn.commit()
    conn.close()


def _ensure_users_and_auth_tables(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id VARCHAR(36) PRIMARY KEY,
        email VARCHAR(255) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        full_name VARCHAR(120) NOT NULL,
        phone VARCHAR(32),
        role VARCHAR(32) NOT NULL DEFAULT 'CUSTOMER',
        status VARCHAR(32) NOT NULL DEFAULT 'active',
        tier VARCHAR(32) NOT NULL DEFAULT 'free',
        is_active BOOLEAN NOT NULL DEFAULT 1,
        is_verified BOOLEAN NOT NULL DEFAULT 1,
        failed_login_attempts INTEGER NOT NULL DEFAULT 0,
        locked_until DATETIME,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_login DATETIME
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_sessions (
        id VARCHAR(36) PRIMARY KEY,
        user_id VARCHAR(36) NOT NULL,
        family_id VARCHAR(36) NOT NULL,
        current_refresh_token_hash VARCHAR(64) NOT NULL,
        device_fingerprint VARCHAR(128),
        ip_address VARCHAR(45),
        user_agent TEXT,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_active_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME NOT NULL,
        revoked_at DATETIME,
        revocation_reason VARCHAR(64),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS refresh_token_records (
        id VARCHAR(36) PRIMARY KEY,
        session_id VARCHAR(36) NOT NULL,
        family_id VARCHAR(36) NOT NULL,
        token_hash VARCHAR(64) UNIQUE NOT NULL,
        is_revoked BOOLEAN NOT NULL DEFAULT 0,
        expires_at DATETIME NOT NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(session_id) REFERENCES user_sessions(id) ON DELETE CASCADE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS auth_audit_logs (
        id VARCHAR(36) PRIMARY KEY,
        timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        event_type VARCHAR(64) NOT NULL,
        status VARCHAR(32) NOT NULL,
        user_id VARCHAR(36),
        actor_role VARCHAR(32),
        ip_address VARCHAR(45),
        user_agent TEXT,
        channel VARCHAR(32) DEFAULT 'WEB',
        reason TEXT,
        metadata JSON DEFAULT '{}'
    );
    """)

    # Seed Superadmin if not exists
    superadmin_id = "00000000-0000-4000-8000-000000000001"
    cur.execute("""
    INSERT OR IGNORE INTO users (
        id, email, password_hash, full_name, phone, role, status, tier, created_at
    ) VALUES (
        ?, 'vasif@kargopilot.az',
        '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHRzdHJpbmc$5V2g+qX8zXp5w8e9s1Q2u3V4w5x6y7z8A9b0C1d2E3f',
        'Vasif Məcidli', '+994776346310', 'SUPER_ADMIN', 'active', 'enterprise', CURRENT_TIMESTAMP
    );
    """, (superadmin_id,))


def _ensure_platform_sessions(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    platforms = [
        ("Temu", "ACTIVE", "Cookie / Persistent Browser Context", "vasif@***.com", "2026-10-14 22:30:00", "2026-11-14 00:00:00", json.dumps({"cookies_count": 42, "user_agent": "Mozilla/5.0 Stealth Chrome", "region": "AZ"})),
        ("Trendyol", "OTP_REQUIRED", "SMS OTP / Bearer Token", "+99477***310", "2026-10-10 14:15:00", "2026-10-14 18:00:00", json.dumps({"step": "awaiting_sms_code", "phone": "+994776346310"})),
        ("Taobao", "DISCONNECTED", "Alibaba QrCode / Cookie", "vasif_m", "2026-09-28 11:00:00", "2026-10-05 00:00:00", json.dumps({"error": "Slide verification required via VNC"})),
        ("1688", "INACTIVE", "API AppKey / Secret", "-", None, None, json.dumps({"note": "Pending merchant API registration"})),
        ("Amazon", "ACTIVE", "Direct Web / 2FA Authenticator", "vasif.mecidli@...", "2026-10-12 09:20:00", "2026-11-12 00:00:00", json.dumps({"otp_device": "Authy 2FA", "marketplace": "Amazon DE / US"})),
        ("SmartCustoms", "ACTIVE", "ASAN Imza / Token / Cookies", "814CRM4", "2026-10-15 10:00:00", "2026-11-15 10:00:00", json.dumps({"asan_cert": "VALID", "fin": "814CRM4", "portal": "smartcustoms.gov.az"})),
    ]
    for p, s, a, u, la, exp, det in platforms:
        cur.execute("""
        INSERT OR REPLACE INTO platform_sessions 
        (platform, status, auth_type, username_hint, last_authenticated_at, expires_at, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (p, s, a, u, la, exp, det))


def _ensure_fin_profiles(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    profiles = [
        ("814CRM4", "Vasif Məcidli", "+994776346310", 1, 300.0, "Əsas istifadəçi FİN hesabı (Vasif Məcidli)"),
    ]
    for fin, name, phone, active, limit_usd, notes in profiles:
        cur.execute("""
        INSERT INTO fin_profiles (fin, full_name, phone, is_active, monthly_limit_usd, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(fin) DO NOTHING;
        """, (fin, name, phone, active, limit_usd, notes))


def _seed_data(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    seed_orders = [
        {
            "id": uuid.uuid4().hex,
            "ref": "PO-014-10523162706552716",
            "platform": "Temu",
            "tracking": "DW5341635",
            "carrier": "STAREX",
            "amount_azn": 48.75,
            "status": "SUBMITTED",
            "order_date": "04.10.2026",
            "created_at": "2026-10-04 10:00:00",
            "items": [
                ("Erqonomik Maşın Kəməri Qoruyucu", "Geyim aksesuarları", "Digər", 2, 4.50, 9.00),
                ("Ultra İncə Şarj Kabeli Type-C (3 metr)", "Telefon və aksesuarları", "Digər", 2, 3.80, 7.60),
                ("Led Maqnitli Gecə Lambası", "Ampüllər/lampalar", "Digər", 1, 12.15, 12.15),
                ("Paslanmayan Polad Termos Fincan 500ml", "Süfrə və mətbəx əşyaları", "Digər", 1, 20.00, 20.00),
            ],
            "customs_ref": "62094812",
            "customs_status": "Bəyan edilib",
            "duty": 0.0,
        },
        {
            "id": uuid.uuid4().hex,
            "ref": "PO-014-09823471829384721",
            "platform": "Temu",
            "tracking": "DW5338868",
            "carrier": "STAREX",
            "amount_azn": 62.30,
            "status": "SUBMITTED",
            "order_date": "08.10.2026",
            "created_at": "2026-10-08 11:30:00",
            "items": [
                ("Silikon Mətbəx Spatula Dəsti 6-lı", "Süfrə və mətbəx əşyaları", "Digər", 1, 14.30, 14.30),
                ("Su Keçirməz Banyo Paspası 50x80", "Tekstil", "Digər", 2, 11.50, 23.00),
                ("Kişi İdman Corabı 5 Cütlük Dəst", "Geyim aksesuarları", "Digər", 2, 6.25, 12.50),
                ("Mini Masaüstü Orqanayzer Rəfi", "Ev aksesuarları (mebel, dekor)", "Digər", 1, 12.50, 12.50),
            ],
            "customs_ref": "62094819",
            "customs_status": "Bəyan edilib",
            "duty": 0.0,
        },
        {
            "id": uuid.uuid4().hex,
            "ref": "TY-9843210984",
            "platform": "Trendyol",
            "tracking": "STRAZ99482103",
            "carrier": "STAREX",
            "amount_azn": 84.50,
            "status": "SUBMITTED",
            "order_date": "11.10.2026",
            "created_at": "2026-10-11 15:45:00",
            "items": [
                ("Pambıq Oversize Qara Hoodie", "Paltar", "Digər", 1, 42.00, 42.00),
                ("Dəri Kişi Kəməri Klassik", "Geyim aksesuarları", "Digər", 1, 24.50, 24.50),
                ("Termal Qış Corabı Qalın", "Geyim aksesuarları", "Digər", 3, 6.00, 18.00),
            ],
            "customs_ref": "62095104",
            "customs_status": "Təsdiqləndi",
            "duty": 0.0,
        },
        {
            "id": uuid.uuid4().hex,
            "ref": "PO-014-11209384728192834",
            "platform": "Temu",
            "tracking": "DW5350912",
            "carrier": "DYNAMEX",
            "amount_azn": 39.80,
            "status": "AWAITING_USER_CONFIRM",
            "order_date": "13.10.2026",
            "created_at": "2026-10-13 18:20:00",
            "items": [
                ("Çoxfunksiyalı Tornavida Dəsti 32-si 1-də", "Təmir-tikinti alətləri", "Digər", 1, 16.80, 16.80),
                ("Optik Simsiz Bluetooth Siçan (Mouse)", "Kompüter və aksesuarları", "Digər", 1, 15.00, 15.00),
                ("Kompüter üçün Mousepad Qara 80x30", "Kompüter və aksesuarları", "Digər", 1, 8.00, 8.00),
            ],
            "customs_ref": "SC-DW5350912",
            "customs_status": "Qaralama (Təsdiq gözləyir)",
            "duty": 0.0,
        },
        {
            "id": uuid.uuid4().hex,
            "ref": "TB-3849102938475",
            "platform": "Taobao",
            "tracking": "LP009847120394",
            "carrier": "ASE",
            "amount_azn": 72.00,
            "status": "STORED",
            "order_date": "14.10.2026",
            "created_at": "2026-10-14 21:05:00",
            "items": [
                ("Anime Masaüstü LED Fiqur Suvenir", "Suvenir və oyuncaqlar", "Digər", 2, 22.50, 45.00),
                ("Xəttatlıq və Rəsm Qələmi Dəsti", "Ofis ləvazimatları", "Digər", 1, 27.00, 27.00),
            ],
            "customs_ref": None,
            "customs_status": None,
            "duty": 0.0,
        }
    ]

    for ord_data in seed_orders:
        extra_json = json.dumps({"order_date": ord_data["order_date"]})
        amount_usd = round(ord_data["amount_azn"] / USD_AZN_RATE, 2)
        created_dt = ord_data["created_at"]

        cur.execute("""
        INSERT OR REPLACE INTO orders 
        (id, platform, temu_order_ref, tracking_number, carrier, receiver_name, receiver_phone, 
         original_amount, original_currency, invoice_amount_azn, invoice_amount_usd, 
         temu_invoice_amount, temu_invoice_currency, status, extra, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'AZN', ?, ?, ?, 'AZN', ?, ?, ?, ?)
        """, (
            ord_data["id"],
            ord_data["platform"],
            ord_data["ref"],
            ord_data["tracking"],
            ord_data["carrier"],
            CONSIGNEE_NAME,
            CONSIGNEE_PHONE,
            ord_data["amount_azn"],
            ord_data["amount_azn"],
            amount_usd,
            ord_data["amount_azn"],
            ord_data["status"],
            extra_json,
            created_dt,
            created_dt,
        ))

        order_id = ord_data["id"]

        for it in ord_data["items"]:
            item_id = uuid.uuid4().hex
            cur.execute("""
            INSERT INTO order_items
            (id, order_id, title, main_cat, sub_cat, quantity, unit_price, retail_price, price_unknown, total_price, currency, unit_price_azn, total_price_azn, total_price_usd, extra)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 'AZN', ?, ?, ?, '{}')
            """, (
                item_id,
                order_id,
                it[0],
                it[1],
                it[2],
                it[3],
                it[4],
                it[4] * 1.2,
                it[5],
                it[4],
                it[5],
                round(it[5] / USD_AZN_RATE, 2),
            ))

        if ord_data.get("customs_ref"):
            decl_id = uuid.uuid4().hex
            payload = json.dumps({
                "tracking_number": ord_data["tracking"],
                "carrier": ord_data["carrier"],
                "status": ord_data["customs_status"],
                "declared": True,
            })
            cur.execute("""
            INSERT OR REPLACE INTO customs_declarations
            (id, order_id, customs_ref, status, payload, duty_estimate_azn, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                decl_id,
                order_id,
                ord_data["customs_ref"],
                ord_data["customs_status"],
                payload,
                ord_data["duty"],
                created_dt,
                created_dt,
            ))


def get_all_orders(
    search: Optional[str] = None,
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Retrieves orders with filtering and item aggregations."""
    conn = get_connection()
    cur = conn.cursor()

    query = """
    SELECT o.*, 
           cd.customs_ref, 
           cd.status AS customs_status, 
           cd.duty_estimate_azn,
           cd.id AS declaration_id,
           COUNT(oi.id) AS item_count
    FROM orders o
    LEFT JOIN customs_declarations cd ON cd.order_id = o.id
    LEFT JOIN order_items oi ON oi.order_id = o.id
    WHERE 1=1
    """
    params: List[Any] = []

    if search:
        s = f"%{search.strip()}%"
        query += " AND (o.temu_order_ref LIKE ? OR o.tracking_number LIKE ? OR o.carrier LIKE ?)"
        params.extend([s, s, s])

    if platform and platform != "ALL":
        query += " AND o.platform = ?"
        params.append(platform)

    if status and status != "ALL":
        query += " AND o.status = ?"
        params.append(status)

    query += " GROUP BY o.id ORDER BY o.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = cur.execute(query, params).fetchall()
    orders = [dict(r) for r in rows]

    # Attach items list
    for ord_dict in orders:
        items_rows = cur.execute(
            "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (ord_dict["id"],)
        ).fetchall()
        ord_dict["items_list"] = [dict(it) for it in items_rows]
        ord_dict["items"] = ord_dict["items_list"]
        ord_dict["item_count"] = len(items_rows)

    conn.close()
    return orders


def get_order_by_id(order_id: Any) -> Optional[Dict[str, Any]]:
    """Fetches a single order with full item list and declaration details."""
    conn = get_connection()
    cur = conn.cursor()

    row = cur.execute("""
    SELECT o.*, 
           cd.customs_ref, 
           cd.status AS customs_status, 
           cd.duty_estimate_azn,
           cd.id AS declaration_id,
           cd.payload AS customs_payload
    FROM orders o
    LEFT JOIN customs_declarations cd ON cd.order_id = o.id
    WHERE o.id = ? OR o.temu_order_ref = ?
    """, (str(order_id), str(order_id))).fetchone()

    if not row:
        conn.close()
        return None

    order_dict = dict(row)
    items_rows = cur.execute(
        "SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_dict["id"],)
    ).fetchall()
    order_dict["items"] = [dict(it) for it in items_rows]

    conn.close()
    return order_dict


def get_all_declarations() -> List[Dict[str, Any]]:
    """Retrieves all customs declarations linked with orders."""
    conn = get_connection()
    cur = conn.cursor()

    rows = cur.execute("""
    SELECT cd.*, 
           o.temu_order_ref, 
           o.tracking_number, 
           o.carrier, 
           o.platform,
           o.temu_invoice_amount,
           o.invoice_amount_azn,
           o.created_at AS order_date
    FROM customs_declarations cd
    LEFT JOIN orders o ON o.id = cd.order_id
    ORDER BY cd.created_at DESC
    """).fetchall()

    decls = [dict(r) for r in rows]
    conn.close()
    return decls


def get_platform_sessions() -> List[Dict[str, Any]]:
    """Fetches all platform connector session statuses."""
    conn = get_connection()
    cur = conn.cursor()
    rows = cur.execute("SELECT * FROM platform_sessions ORDER BY platform").fetchall()
    sessions = []
    for r in rows:
        d = dict(r)
        if d.get("details"):
            try:
                d["details_parsed"] = json.loads(d["details"])
            except Exception:
                d["details_parsed"] = {}
        else:
            d["details_parsed"] = {}
        sessions.append(d)
    conn.close()
    return sessions


def get_db_metrics() -> Dict[str, Any]:
    """Returns database size, table counts, and storage metrics."""
    conn = get_connection()
    cur = conn.cursor()

    order_count = cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    item_count = cur.execute("SELECT COUNT(*) FROM order_items").fetchone()[0]
    decl_count = cur.execute("SELECT COUNT(*) FROM customs_declarations").fetchone()[0]
    session_count = cur.execute("SELECT COUNT(*) FROM platform_sessions").fetchone()[0]

    # File size in MB
    db_size_mb = 0.0
    if DB_PATH.exists():
        db_size_mb = round(DB_PATH.stat().st_size / (1024 * 1024), 3)

    integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]

    conn.close()
    return {
        "db_path": str(DB_PATH),
        "db_size_mb": db_size_mb,
        "integrity": integrity,
        "counts": {
            "orders": order_count,
            "order_items": item_count,
            "customs_declarations": decl_count,
            "platform_sessions": session_count,
        }
    }


def get_fin_profiles() -> List[Dict[str, Any]]:
    """Retrieves all registered FIN profiles with active flag and monthly limits."""
    conn = get_connection()
    cur = conn.cursor()
    rows = cur.execute("SELECT * FROM fin_profiles ORDER BY is_active DESC, created_at ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_fin() -> Dict[str, Any]:
    """Returns the currently active FIN profile for declaration routing."""
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM fin_profiles WHERE is_active = 1 LIMIT 1").fetchone()
    if not row:
        row = cur.execute("SELECT * FROM fin_profiles ORDER BY created_at ASC LIMIT 1").fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"fin": "814CRM4", "full_name": "Vasif Məcidli", "monthly_limit_usd": 300.0, "is_active": 1}


def switch_active_fin(target_fin: str) -> Dict[str, Any]:
    """Switches the active customs declaration profile to target_fin."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE fin_profiles SET is_active = 0")
    cur.execute("UPDATE fin_profiles SET is_active = 1 WHERE fin = ?", (target_fin.strip().upper(),))
    conn.commit()
    active = get_active_fin()
    conn.close()
    return {
        "ok": True,
        "active_fin": active["fin"],
        "full_name": active["full_name"],
        "message": f"Aktiv FİN profili dəyişdirildi: {active['full_name']} ({active['fin']})"
    }


def get_category_cache(title_hash: str) -> Optional[Tuple[str, str]]:
    """Looks up category classification from SQLite product_category_cache."""
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute(
        "SELECT main_cat, sub_cat FROM product_category_cache WHERE title_hash = ?",
        (title_hash,)
    ).fetchone()
    conn.close()
    if row:
        return row[0], row[1]
    return None


def save_category_cache(
    title_hash: str,
    raw_title: str,
    main_cat: str,
    sub_cat: str = "Digər",
    source: str = "deterministic"
) -> None:
    """Persists category classification to SQLite product_category_cache."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    INSERT OR REPLACE INTO product_category_cache (title_hash, raw_title, main_cat, sub_cat, source)
    VALUES (?, ?, ?, ?, ?)
    """, (title_hash, raw_title, main_cat, sub_cat, source))
    conn.commit()
    conn.close()

