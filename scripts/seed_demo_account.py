"""Script to seed/ensure the official KargoPilot Demo Account on local or VPS database.
User: demo@kargopilot.az / KargoPilot2026! / FIN: 7KP2026
Contains 2 active parcels totaling $260.00 USD (DGK 300$ Warning status).
Etap 7: Seeds active external sessions (Trendyol, Starex, SmartCustoms) and 1-click customs declaration.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Try to find the db path
possible_paths = [
    Path("/data/pcs/pcs.db"),
    Path(__file__).resolve().parent.parent / "web_panel" / "pcs.db",
    Path("pcs.db"),
]

db_path = None
for p in possible_paths:
    if p.exists() or str(p).startswith("/data/pcs"):
        db_path = p
        break

if not db_path:
    db_path = Path("pcs.db")

print(f"Targeting Database at: {db_path}")

# Import password hasher
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "web_panel"))
try:
    from app.security.crypto import password_manager
    hashed_pwd = password_manager.hash_password("KargoPilot2026!")
except Exception:
    import bcrypt
    hashed_pwd = bcrypt.hashpw("KargoPilot2026!".encode(), bcrypt.gensalt(12)).decode()

conn = sqlite3.connect(str(db_path), timeout=30.0)
conn.row_factory = sqlite3.Row

try:
    from app.database import _ensure_users_and_auth_tables, _ensure_etap6_tables, _ensure_etap7_tables
    _ensure_users_and_auth_tables(conn)
    _ensure_etap6_tables(conn)
    _ensure_etap7_tables(conn)
    conn.commit()
except Exception as e:
    print(f"Warning running schema ensure: {e}")

user_id = "demo-user-7kp2026"
email = "demo@kargopilot.az"
full_name = "KargoPilot Demo İstifadəçisi"
phone = "+994501234567"
fin = "7KP2026"
branch = "Bakı - Mərkəz (28 May Filialı)"
now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

# 1. Upsert User
conn.execute("""
INSERT INTO users (
    id, email, password_hash, full_name, phone, role, status, tier,
    is_active, is_verified, failed_login_attempts, fin, default_branch,
    notification_whatsapp, notification_email, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, 'CUSTOMER', 'active', 'cloud_managed', 1, 1, 0, ?, ?, 1, 1, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    email = excluded.email,
    password_hash = excluded.password_hash,
    full_name = excluded.full_name,
    phone = excluded.phone,
    fin = excluded.fin,
    default_branch = excluded.default_branch,
    notification_whatsapp = 1,
    notification_email = 1,
    updated_at = excluded.updated_at
""", (user_id, email, hashed_pwd, full_name, phone, fin, branch, now_str, now_str))

# Also ensure by email if id was different
conn.execute("""
UPDATE users SET 
    password_hash = ?, full_name = ?, phone = ?, fin = ?, default_branch = ?,
    role = 'CUSTOMER', status = 'active', tier = 'cloud_managed',
    is_active = 1, failed_login_attempts = 0, updated_at = ?
WHERE LOWER(email) = ?
""", (hashed_pwd, full_name, phone, fin, branch, now_str, email.lower()))

# 2. Reset and seed parcels for demo user
orders = conn.execute("SELECT id FROM orders WHERE user_id = ?", (user_id,)).fetchall()
order_ids = [r["id"] for r in orders]
if order_ids:
    placeholders = ",".join("?" for _ in order_ids)
    conn.execute(f"DELETE FROM order_items WHERE order_id IN ({placeholders})", order_ids)
    conn.execute("DELETE FROM orders WHERE user_id = ?", (user_id,))

# Seed Parcel 1: $85.00 USD (Already Declared to SmartCustoms)
order1_id = f"demo-ord-01-{uuid.uuid4().hex[:6]}"
conn.execute("""
INSERT INTO orders (
    id, user_id, platform, temu_order_ref, tracking_number, carrier,
    receiver_name, receiver_phone, fin, original_amount, original_currency,
    fx_rate_to_azn, fx_rate_to_usd, invoice_amount_azn, invoice_amount_usd,
    temu_invoice_amount, temu_invoice_currency, status, extra, 
    declared_to_dgk, dgk_declaration_id, declared_at, declaration_fin,
    created_at, updated_at
) VALUES (?, ?, 'Trendyol', ?, 'TRK-TY984120', 'STAREX', ?, ?, ?, 144.50, 'AZN', 1.0, 0.5882, 144.50, 85.00, 144.50, 'AZN', 'Bəyan edilib ✓', '{}', 1, 'DGK-2026-DEMO01', ?, ?, ?, ?)
""", (order1_id, user_id, f"TY-{uuid.uuid4().hex[:8]}", full_name, phone, fin, now_str, fin, now_str, now_str))

conn.execute("""
INSERT INTO order_items (
    id, order_id, title, main_cat, sub_cat, quantity, unit_price, price_unknown,
    total_price, currency, unit_price_azn, total_price_azn, total_price_usd, extra
) VALUES (?, ?, 'Kişi Qış Gödəkcəsi və İdman Ayaqqabısı', 'Geyim aksesuarları', 'Digər', 1, 144.50, 0, 144.50, 'AZN', 144.50, 144.50, 85.00, '{}')
""", (str(uuid.uuid4()), order1_id))

# Seed Parcel 2: $175.00 USD (In Transit, Ready for 1-Click Declaration)
order2_id = f"demo-ord-02-{uuid.uuid4().hex[:6]}"
conn.execute("""
INSERT INTO orders (
    id, user_id, platform, temu_order_ref, tracking_number, carrier,
    receiver_name, receiver_phone, fin, original_amount, original_currency,
    fx_rate_to_azn, fx_rate_to_usd, invoice_amount_azn, invoice_amount_usd,
    temu_invoice_amount, temu_invoice_currency, status, extra,
    declared_to_dgk, dgk_declaration_id, declared_at, declaration_fin,
    created_at, updated_at
) VALUES (?, ?, 'Amazon', ?, 'AMZ-441029US', 'CAMEX', ?, ?, ?, 297.50, 'AZN', 1.0, 0.5882, 297.50, 175.00, 297.50, 'AZN', 'Yoldadır ✈️', '{}', 0, NULL, NULL, NULL, ?, ?)
""", (order2_id, user_id, f"AMZ-{uuid.uuid4().hex[:8]}", full_name, phone, fin, now_str, now_str))

conn.execute("""
INSERT INTO order_items (
    id, order_id, title, main_cat, sub_cat, quantity, unit_price, price_unknown,
    total_price, currency, unit_price_azn, total_price_azn, total_price_usd, extra
) VALUES (?, ?, 'Sony Simsiz Səs Qulaqlığı (ANC)', 'Elektronika', 'Digər', 1, 297.50, 0, 297.50, 'AZN', 297.50, 297.50, 175.00, '{}')
""", (str(uuid.uuid4()), order2_id))

# 3. Update fin_profiles
conn.execute("""
INSERT INTO fin_profiles (fin, full_name, phone, is_active, monthly_limit_usd, notes)
VALUES (?, ?, ?, 1, 300.0, 'Demo Pilot İstifadəçi Profili')
ON CONFLICT(fin) DO UPDATE SET full_name = excluded.full_name, phone = excluded.phone
""", (fin, full_name, phone))

# 4. Etap 6: Custom Store for Demo User
conn.execute("DELETE FROM user_stores WHERE user_id = ? AND is_standard = 0", (user_id,))
conn.execute("""
INSERT INTO user_stores (id, user_id, name, domain_url, country_code, default_currency, category, icon_badge, is_standard, login_url, auth_method, created_at)
VALUES (?, ?, 'Morhipo VIP', 'https://morhipo.com', 'TR', 'TRY', 'Geyim', '👗', 0, 'https://morhipo.com/giris', 'credentials_otp', ?)
""", (f"demo-store-{uuid.uuid4().hex[:6]}", user_id, now_str))

# 5. Etap 6: Custom Carrier for Demo User
conn.execute("DELETE FROM user_carriers WHERE user_id = ? AND is_standard = 0", (user_id,))
conn.execute("""
INSERT INTO user_carriers (id, user_id, name, website_url, tracking_url_template, origin_country, rate_per_kg_usd, liquid_surcharge_usd, electronics_surcharge_usd, delivery_days_min, delivery_days_max, branch_address, is_standard, login_url, auth_method, created_at)
VALUES (?, ?, 'KargoPilot Super Ekspres TR', 'https://superekspres.az', 'https://superekspres.az/track/{tracking}', 'TR', 2.75, 1.0, 1.5, 2, 4, '28 May Mərkəzi Filial', 0, 'https://superekspres.az/login', 'credentials_otp', ?)
""", (f"demo-carr-{uuid.uuid4().hex[:6]}", user_id, now_str))

# 6. Etap 6: Family FIN Mesh for Demo User
conn.execute("DELETE FROM family_fins WHERE user_id = ?", (user_id,))
conn.execute("""
INSERT INTO family_fins (id, user_id, name_relation, fin, monthly_limit_usd, spent_usd, created_at)
VALUES (?, ?, 'Aygün Məcidli (Həyat yoldaşı)', '7AY2026', 300.0, 40.0, ?)
""", (f"demo-ffin-{uuid.uuid4().hex[:6]}", user_id, now_str))

# 7. Etap 6: AI Chat Welcome Turn for Demo User
conn.execute("DELETE FROM ai_chat_messages WHERE user_id = ?", (user_id,))
conn.execute("""
INSERT INTO ai_chat_messages (id, user_id, role, content, created_at)
VALUES (?, ?, 'user', 'Salam Loyd, 300$ limitim necədir?', ?)
""", (f"demo-aimsg-1-{uuid.uuid4().hex[:6]}", user_id, now_str))
conn.execute("""
INSERT INTO ai_chat_messages (id, user_id, role, content, created_at)
VALUES (?, ?, 'assistant', 'Salam Vasif bəy! Cari ayda 2 bağlamanız üzrə 260.00 USD xərcləmisiniz. Aylıq 300$ limitinizdən 40.00 USD (68.00 AZN) qalıq ehtiyatınız var. Əlavə olaraq ailə FİN şəbəkənizdə Aygün xanımın (7AY2026) 260.00 USD sərbəst limiti mövcuddur.', ?)
""", (f"demo-aimsg-2-{uuid.uuid4().hex[:6]}", user_id, now_str))

# 8. Etap 7: External Connected Sessions Vault
conn.execute("DELETE FROM external_sessions WHERE user_id = ?", (user_id,))

# Seed Trendyol Session
conn.execute("""
INSERT INTO external_sessions (
    id, user_id, provider_type, provider_key, provider_name, login_url,
    account_identifier, auth_method, session_payload_encrypted, session_status,
    last_synced_at, expires_at, sync_summary_json, created_at, updated_at
) VALUES (
    ?, ?, 'store', 'trendyol', 'Trendyol TR', 'https://www.trendyol.com/giris',
    'demo.trendyol@kargopilot.az', 'credentials_otp', 'ENCRYPTED_TRENDYOL_VAULT_PAYLOAD',
    'active', ?, datetime('now', '+30 days'), '{"synced_items": 2}', ?, ?
)
""", (f"demo-sess-ty-{uuid.uuid4().hex[:6]}", user_id, now_str, now_str, now_str))

# Seed Starex Session
conn.execute("""
INSERT INTO external_sessions (
    id, user_id, provider_type, provider_key, provider_name, login_url,
    account_identifier, auth_method, session_payload_encrypted, session_status,
    last_synced_at, expires_at, sync_summary_json, created_at, updated_at
) VALUES (
    ?, ?, 'carrier', 'starex', 'Starex Global', 'https://starex.az/login',
    '+994501234567', 'credentials_otp', 'ENCRYPTED_STAREX_VAULT_PAYLOAD',
    'active', ?, datetime('now', '+30 days'), '{"synced_items": 2}', ?, ?
)
""", (f"demo-sess-strx-{uuid.uuid4().hex[:6]}", user_id, now_str, now_str, now_str))

# Seed SmartCustoms Session
conn.execute("""
INSERT INTO external_sessions (
    id, user_id, provider_type, provider_key, provider_name, login_url,
    account_identifier, auth_method, session_payload_encrypted, session_status,
    last_synced_at, expires_at, sync_summary_json, created_at, updated_at
) VALUES (
    ?, ?, 'smartcustoms', 'smartcustoms', 'Dövlət Gömrük Komitəsi (SmartCustoms)', 'https://e.customs.gov.az',
    '7KP2026', 'sima', 'ENCRYPTED_SMARTCUSTOMS_SIMA_TOKEN',
    'active', ?, datetime('now', '+30 days'), '{"active_declarations": 1}', ?, ?
)
""", (f"demo-sess-sc-{uuid.uuid4().hex[:6]}", user_id, now_str, now_str, now_str))

conn.commit()
conn.close()
print("[OK] Demo Account seeded successfully:")
print(f"  Email: {email}")
print(f"  Password: KargoPilot2026!")
print(f"  FIN: {fin}")
print(f"  Parcels: 2 ($85.00 + $175.00 = $260.00 USD, Warning status, 1 Declared)")
print("  Custom Store: Morhipo VIP (TR)")
print("  Custom Carrier: KargoPilot Super Ekspres TR ($2.75/kq)")
print("  Family FIN: 7AY2026 - Aygun Mecidli ($260 qaliq)")
print("  AI Copilot: Welcome conversation history primed.")
print("  Etap 7 Sessions: Trendyol (store: active), Starex (carrier: active), SmartCustoms (active).")
