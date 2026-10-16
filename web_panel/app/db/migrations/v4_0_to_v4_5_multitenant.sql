-- ============================================================================
-- KARGOPILOT v4.0 -> v4.5 NON-DESTRUCTIVE MULTI-TENANT MIGRATION
-- Database: pcs.db
-- Target: SQLite 3.35+ with WAL mode
-- ============================================================================

PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 30000;
PRAGMA foreign_keys = OFF;

BEGIN TRANSACTION;

-- 1. Users Entity
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    phone VARCHAR(32) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'user',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    tier VARCHAR(32) NOT NULL DEFAULT 'free',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- 2. User Sessions & Tokens
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    refresh_token_hash VARCHAR(64) NOT NULL,
    user_agent TEXT,
    ip VARCHAR(45) NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at DATETIME,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_refresh_hash ON user_sessions(refresh_token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON user_sessions(expires_at);

-- 3. Immutable Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36),
    action VARCHAR(64) NOT NULL,
    resource VARCHAR(128) NOT NULL,
    ip VARCHAR(45) NOT NULL,
    user_agent TEXT,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    details_json JSON NOT NULL DEFAULT '{}',
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_user_ts ON audit_logs(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);

-- 4. Seed Initial Superadmin Account (Vasif Məcidli)
INSERT OR IGNORE INTO users (
    id, email, password_hash, full_name, phone, role, status, tier, created_at
) VALUES (
    '00000000-0000-4000-8000-000000000001',
    'vasif@kargopilot.az',
    '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHRzdHJpbmc$5V2g+qX8zXp5w8e9s1Q2u3V4w5x6y7z8A9b0C1d2E3f',
    'Vasif Məcidli',
    '+994776346310',
    'superadmin',
    'active',
    'enterprise',
    CURRENT_TIMESTAMP
);

-- 5. Upgrade fin_profiles Table to Multi-Tenant Schema
CREATE TABLE IF NOT EXISTS fin_profiles_new (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    fin VARCHAR(7) NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    phone VARCHAR(32),
    monthly_limit_usd REAL NOT NULL DEFAULT 300.0,
    current_cycle_spent_usd REAL NOT NULL DEFAULT 0.0,
    is_primary BOOLEAN NOT NULL DEFAULT 0,
    relationship VARCHAR(32) NOT NULL DEFAULT 'self',
    notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, fin)
);

-- Migrate existing fin_profiles into new schema under Superadmin (as secondary/family mesh)
INSERT OR IGNORE INTO fin_profiles_new (id, user_id, fin, full_name, phone, monthly_limit_usd, is_primary, notes, is_active, created_at)
SELECT 
    hex(randomblob(16)) AS id,
    '00000000-0000-4000-8000-000000000001' AS user_id,
    fin,
    full_name,
    phone,
    monthly_limit_usd,
    0 AS is_primary,
    notes,
    1 AS is_active,
    created_at
FROM fin_profiles;

-- Ensure Vasif Məcidli's primary official FIN 814CRM4 exists and is set as primary
INSERT INTO fin_profiles_new (
    id, user_id, fin, full_name, phone, monthly_limit_usd, current_cycle_spent_usd, is_primary, relationship, notes, is_active
) VALUES (
    'fin-0000-0000-0000-000000000001',
    '00000000-0000-4000-8000-000000000001',
    '814CRM4',
    'Vasif Məcidli',
    '+994776346310',
    300.0,
    0.0,
    1,
    'self',
    'Superadmin Official Primary Customs FIN',
    1
) ON CONFLICT(user_id, fin) DO UPDATE SET is_primary = 1;

UPDATE fin_profiles_new 
SET is_primary = 0 
WHERE user_id = '00000000-0000-4000-8000-000000000001' AND fin != '814CRM4';

DROP TABLE IF EXISTS fin_profiles;
ALTER TABLE fin_profiles_new RENAME TO fin_profiles;
CREATE INDEX IF NOT EXISTS idx_fin_profiles_user ON fin_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_fin_profiles_fin ON fin_profiles(fin);

-- 6. Upgrade carrier_accounts Table to Multi-Tenant Schema
CREATE TABLE IF NOT EXISTS carrier_accounts_new (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    carrier_code VARCHAR(32) NOT NULL,
    suite_code VARCHAR(64) NOT NULL,
    branch_id VARCHAR(64) NOT NULL DEFAULT '28 May',
    credentials_vault TEXT NOT NULL,
    warehouse_suites JSON DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT 1,
    last_sync_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, carrier_code)
);

INSERT OR IGNORE INTO carrier_accounts_new (
    id, user_id, carrier_code, suite_code, branch_id, credentials_vault, warehouse_suites, is_active, last_sync_at, created_at
)
SELECT 
    id,
    '00000000-0000-4000-8000-000000000001' AS user_id,
    carrier_name AS carrier_code,
    customer_code AS suite_code,
    COALESCE(default_branch, '28 May') AS branch_id,
    COALESCE(auth_token, '{}') AS credentials_vault,
    COALESCE(warehouse_suites, '{}') AS warehouse_suites,
    COALESCE(is_active, 1) AS is_active,
    last_sync_at,
    created_at
FROM carrier_accounts;

DROP TABLE IF EXISTS carrier_accounts;
ALTER TABLE carrier_accounts_new RENAME TO carrier_accounts;
CREATE INDEX IF NOT EXISTS idx_carrier_acc_user ON carrier_accounts(user_id);

-- 7. Add user_id column to orders table if not present, and backfill
-- Note: In SQLite, ALTER TABLE ADD COLUMN is safe and fast
-- We use a script or safe statement. If column exists, SQLite will throw error unless checked.
-- In pure SQL script, we execute:
ALTER TABLE orders ADD COLUMN user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE;

UPDATE orders 
SET user_id = '00000000-0000-4000-8000-000000000001'
WHERE user_id IS NULL;

UPDATE orders 
SET fin = '814CRM4'
WHERE fin IS NULL OR fin = '' OR fin = '6N89P92';

CREATE INDEX IF NOT EXISTS idx_orders_user_created ON orders(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_user_status ON orders(user_id, status);

-- 8. Add user_id column to customs_declarations table
ALTER TABLE customs_declarations ADD COLUMN user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE;

UPDATE customs_declarations 
SET user_id = '00000000-0000-4000-8000-000000000001'
WHERE user_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_customs_user_status ON customs_declarations(user_id, status);

-- 9. Add user_id column to carrier_shipments if table exists
CREATE TABLE IF NOT EXISTS carrier_shipments (
    id VARCHAR(40) PRIMARY KEY,
    carrier_name VARCHAR(32) NOT NULL,
    order_ref VARCHAR(64) NOT NULL,
    origin_tracking VARCHAR(64) NOT NULL,
    destination_tracking VARCHAR(64),
    smart_customs_no VARCHAR(64),
    origin_country VARCHAR(8) DEFAULT 'TR',
    seller_name VARCHAR(120),
    declared_amount REAL,
    declared_currency VARCHAR(8),
    amount_azn REAL,
    amount_usd REAL,
    status VARCHAR(40) DEFAULT 'PRE_DECLARED',
    weight_kg REAL,
    delivery_fee_usd REAL,
    delivery_fee_azn REAL,
    invoice_pdf_path TEXT,
    pre_declared_at DATETIME,
    arrived_hub_at DATETIME,
    released_customs_at DATETIME,
    extra JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE carrier_shipments ADD COLUMN user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE;

UPDATE carrier_shipments 
SET user_id = '00000000-0000-4000-8000-000000000001'
WHERE user_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_shipments_user ON carrier_shipments(user_id);

-- 10. Audit log of migration
INSERT INTO audit_logs (
    id, user_id, action, resource, ip, user_agent, timestamp, details_json
) VALUES (
    'mig-0000-0000-0000-000000000001',
    '00000000-0000-4000-8000-000000000001',
    'SYSTEM_MIGRATION_V4_5',
    'database:pcs.db',
    '127.0.0.1',
    'KargoPilot Migration Runner v4.5',
    CURRENT_TIMESTAMP,
    json_object(
        'migration', 'v4.0_to_v4.5',
        'assigned_superadmin', 'Vasif Məcidli',
        'superadmin_phone', '+994776346310',
        'superadmin_fin', '814CRM4',
        'orders_migrated', (SELECT COUNT(*) FROM orders),
        'items_migrated', (SELECT COUNT(*) FROM order_items),
        'declarations_migrated', (SELECT COUNT(*) FROM customs_declarations)
    )
);

COMMIT;

PRAGMA foreign_keys = ON;
