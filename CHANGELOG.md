# Changelog

All notable changes to the **KargoPilot** autonomous cross-border logistics and customs copilot platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [6.5.0] - 2026-10-17

### 🚀 Major Release: 1-Click Session Quick-Bridge, Unified 4-Channel Health Diagnostics, Dual-Hosting First-Screen Polish & Full GitHub Repo Sync (`Etap 9`)

KargoPilot v6.5.0 introduces the 1-Click Session Quick-Bridge (`POST /api/v1/user/sessions/quick-bridge`), unified 4-channel health diagnostics (`GET /api/v1/user/channels/health-summary`), a cohesive Dual-Hosting first-screen experience (`/`, `/onboarding`, `/self-hosted` -> `/user/dashboard`), and full v6.5.0 synchronization across all repository documentation and deployment configs:

### ✨ Added
- **1-Click Session Quick-Bridge (`POST /api/v1/user/sessions/quick-bridge`)**:
  - Connects Store, Carrier, or SmartCustoms sessions in a single click without manual cookie copying or console commands.
  - Enforces strict SSRF validation, Fernet 256-bit encryption in `external_sessions`, masked account identifiers (`m***@kargopilot.az`, `7K***26`), and immediate Read-Only connection verification (`session_status: "active"`, `connection_alive: True`, `read_only_safe_mode: True`).
- **Unified 4-Channel Health Diagnostics (`GET /api/v1/user/channels/health-summary`)**:
  - Single-request diagnostic summary returning live readiness and metadata for all 4 channels (`store_channel`, `carrier_channel`, `smartcustoms_channel`, `whatsapp_channel`) alongside `overall_health_score` (`0–100%`).
  - SmartCustoms channel strictly enforces `read_only_safe_mode: True` and `declarations_created: 0` (Bəyannaməsiz Təhlükəsiz Oxuma və Əlaqə Aktuallığı Rejimi).
- **Unified Dual-Hosting First-Screen Flow (`/`, `/onboarding`, `/self-hosted` -> `/user/dashboard`)**:
  - Upgraded `self_hosted.html` with `taste-skill` and `ui-ux-pro-max` tokens (`.tabular-nums`, `.kp-glass-card`, `cubic-bezier(0.16, 1, 0.3, 1)`), interactive **"Hansı Rejim Mənə Uyğundur?"** selector, 1-Click Docker Compose setup wizard, and 4-channel readiness badges on node verification (`POST /api/v1/system/verify-node`).
- **Etap 9 Unified Release & Bridge E2E Suite (`tests/test_etap9_unified_release_and_bridge_e2e.py`)**:
  - Added 5 comprehensive E2E tests covering v6.5 repo documentation/config compliance, Dual-Hosting first-screen to dashboard journey, 1-Click Quick-Bridge + 4-Channel Health Summary, SmartCustoms Read-Only enforcement + AI Copilot 4-channel awareness, and Dual-Router/Template byte-for-byte sync + Zero-Leak audit (`97/97` total tests passing).

---

## [6.0.0] - 2026-10-17

### 🚀 Major Release: 4-Channel Unified Connection Health Matrix, SmartCustoms Read-Only Safe Mode, WhatsApp Gateway & High-Craft UI (`taste-skill` + `ui-ux-pro-max`)

KargoPilot v6.0.0 unifies all external integrations into a live 4-channel health matrix, enforces strict Read-Only safety for SmartCustoms liveness & $300 quota checks, adds a dedicated WhatsApp Notification Gateway, and elevates the entire web UI with `taste-skill` and `ui-ux-pro-max` standards:

### ✨ Added
- **4-Channel Unified Connection Health Matrix (`#unified-connection-health-matrix`)**:
  - Live 4-card Bento status header on `/user/dashboard` tracking:
    1. **🏪 Mağaza Əlaqəsi (`store`)**: Active marketplace session status, OTP verification state, and order sync telemetry.
    2. **🚚 Kargo Əlaqəsi (`carrier`)**: Active freight forwarder session status and foreign warehouse sync telemetry.
    3. **🏛️ SmartCustoms Read-Only (`smartcustoms`)**: Live DGK connection liveness and $300 monthly quota verification.
    4. **💬 WhatsApp Bildiriş Şlüzü (`whatsapp`)**: Bound `+994XXXXXXXXX` gateway liveness, alert preferences, and 1-click ping test.
- **SmartCustoms Read-Only Safe Mode (`POST /api/v1/user/smartcustoms/check-connection` & `/sync`)**:
  - Enforces **`read_only_safe_mode: True`** (`declarations_created: 0` — Bəyannaməsiz Təhlükəsiz Oxuma Rejimi).
  - Strictly verifies session validity (`connection_alive: True`, `session_valid: True`), response latency (`latency_ms`), and $300 USD monthly DGK quota status without submitting new customs declarations.
- **WhatsApp Notification & Liveness Gateway (`/api/v1/user/whatsapp/*`)**:
  - `GET /api/v1/user/whatsapp/status`: Returns bound masked phone (`+9945***4567`), gateway status, and notification preferences.
  - `POST /api/v1/user/whatsapp/connect`: Validates `+994XXXXXXXXX` phone numbers, persists notification preferences (`parcel_arrival`, `customs_300_warning`, `session_expiry_alert`), and stores Fernet-encrypted session state in `external_sessions`.
  - `POST /api/v1/user/whatsapp/ping`: Executes a live gateway ping returning `delivered_simulation: True`, `gateway_reachable: True`, `latency_ms`, and message preview.
- **🤖 4-Channel Context-Aware Loyd AI Copilot (`/api/v1/user/ai/chat`)**:
  - Upgraded `generate_copilot_response` with real-time `channels_health` context so Loyd AI reports the live connection status of Store, Carrier, SmartCustoms (Read-Only), and WhatsApp alongside the user's $300 DGK quota balance.
- **High-Craft UI/UX Polish (`taste-skill` & `ui-ux-pro-max`)**:
  - Applied `font-variant-numeric: tabular-nums` (`.tabular-nums`), `1px solid rgba(255, 255, 255, 0.08)` glassmorphic refraction borders (`.kp-glass-card`), `cubic-bezier(0.16, 1, 0.3, 1)` transitions, and WCAG AAA `role="alert"` / `role="dialog"` accessibility across `user_dashboard.html`, `login.html`, and `register.html`.
- **Comprehensive Etap 8 E2E Test Suite (`tests/test_etap8_full_system_and_connections_e2e.py`)**:
  - Added 7 full-lifecycle E2E tests verifying registration/login, store/carrier OTP & sync, SmartCustoms Read-Only safety (`declarations_created == 0`), WhatsApp connect/ping, 4-channel AI Copilot awareness, Dual-Router/Template byte-for-byte sync, and Zero-Leak compliance.
  - Full test suite expanded to **92/92 passing tests locally (100%)** and **54/54 Etap 1–8 tests on live VPS**.

---

## [5.5.0] - 2026-10-17

### 🚀 Major Release: Interactive Session Vault, SmartCustoms Auth-Bridge, and Dual-Hosting Alignment

KargoPilot v5.5 introduced encrypted marketplace/forwarder session management, SmartCustoms session verification, and full-spectrum end-to-end user journeys:

### ✨ Added
- **Interactive Session Vault (`/sessions/*`)**:
  - Fernet AES-256 cryptographic vault for third-party marketplace and forwarder sessions (Trendyol, Temu, Amazon, Starex, Expargo, Camex, and SmartCustoms).
  - Universal interactive modal supporting credentials handshake, OTP 2FA challenge resolution, and order synchronization.
  - Zero Secret Leak: masked identification tokens (`****`) across all public JSON API surfaces; strict IDOR and SSRF defense boundaries preventing intranet exploitation.
- **SmartCustoms Session & Quota Bridge (`/smartcustoms/*`)**:
  - Electronic customs quota and declaration status tracking conforming to Cabinet of Ministers Decision No. 305 (operated in `read_only_safe_mode: True` in v6.0 for safe connection and $300 quota verification).
- **Pre-Seeded Production Demo Account**:
  - Out-of-the-box demonstration account (`demo@kargopilot.az` / `KargoPilotDemo2026!` or `KargoPilot2026!` / FİN `7KP2026`) equipped with active sessions and realistic parcel telemetry.
- **Automated Verification**:
  - Added `tests/test_etap7_interactive_sessions_and_sync_flow.py` covering session lifecycle, OTP verification, IDOR isolation, and zero-leak boundary tests.

---

## [5.0.0] - 2026-10-16

### 🚀 Major Release: Stores & Carriers Ecosystem Hub, AI Copilot, and Smart Arbitrage / Customs Supervisor

### ✨ Added
- **Stores & Forwarders Ecosystem Hub (`/stores`, `/carriers`)**:
  - Dynamic user-managed store catalog (Trendyol, Temu, Amazon, Zara, Hepsiburada, Shein, iHerb, AliExpress, etc.).
  - User-managed forwarder accounts with custom branch routing across 76+ Baku and regional pickup hubs.
- **Autonomous AI Copilot (`/api/v1/user/ai/chat`)**:
  - Context-aware logistics assistant conversant in natural Azerbaijani, trained on customs regulations, prohibited commodities (drones, lithium batteries, dangerous liquids), and multi-carrier cost optimizations.
- **Smart Arbitrage Engine (`/api/v1/user/arbitrage/calculate`)**:
  - Multi-carrier rate comparison (Starex, Expargo, Camex, Dynamex, Limak, Mover, KoliPlus) across Turkey, USA, China, and Europe origins.
  - Real-time volumetric ($L \times W \times H / 6000$) vs physical weight comparison with USD and CBAR AZN (1.7000) conversions.
- **Customs Supervisor & Duty Simulator (`/api/v1/user/customs/*`)**:
  - Real-time rolling 30-day $300 USD duty-free quota monitoring with visual safety zones (Green, Amber, Crimson).
  - 36% unified customs tariff + 15 AZN processing fee simulator for parcels exceeding the legal exemption limit.
- **Data Portability & Self-Hosted Control (`/api/v1/user/data/*`)**:
  - Full JSON export of user profiles, FIN records, and parcel histories.
  - Cryptographically confirmed account purge (Right to be Forgotten).
  - Validated JSON data re-import flow.
- **Advanced User Dashboard & Bento UI (`/user/dashboard`)**:
  - Modernized user interface featuring responsive glassmorphic Bento cards, quick-copy addresses, and family quota distributions.

---

## [4.5.0] - 2026-10-16

### 🚀 Major Release: Dual-Architecture Self-Hosted & Cloud Platform, Multi-Tenant Auth, and Admin Cockpit

KargoPilot v4.5 introduces a flexible dual-tier deployment paradigm, enterprise multi-tenant authentication, and an executive administration cockpit (`/admin`):

### ✨ Added
- **Dual Deployment Architecture**:
  - **Variant 1 (Müstəqil Server / Self-Hosted)**: Complete on-premise deployment via `docker-compose.sovereign.yml` and 1-click installer (`install_sovereign.sh`, `setup_sovereign.ps1`). Zero data or telemetry sent to company servers; total ownership over FIN codes, passwords, WhatsApp sessions, and carrier keys.
  - **Variant 2 (Managed Cloud 7/24 SaaS)**: Multi-tenant managed cloud deployment with per-tenant AES-256 envelope encryption, 7/24 SmartCustoms quota monitoring, high availability, and legal compliance (AR "Fərdi məlumatlar haqqında" Qanunu).
- **Enterprise Multi-Tenant Security Stack**:
  - **Argon2id Hashing**: High-work-factor password security with transparent auto-migration from legacy bcrypt without forcing user password resets.
  - **Dual-Token Authentication**: Short-lived Access Tokens (HTTP-only SameSite cookies / Bearer headers) paired with rotating Refresh Tokens featuring Token Family Reuse Detection.
  - **Role-Based Access Control (RBAC)**: Comprehensive permission matrix across `SUPER_ADMIN`, `ADMIN/OPERATOR`, and `CUSTOMER` with automatic SQL tenant scoping.
  - **Admin Command Gate (WhatsApp)**: Incoming WhatsApp admin commands (`!admin`) are silently obfuscated for unauthorized users ("Naməlum komanda") to conceal admin capability existence while logging an internal security audit event.
- **Enterprise Admin Cockpit (`/admin`)**:
  - **Executive Command Center (`/admin`)**: Live telemetry, total registered users, in-flight parcels, DGK customs volume, net arbitrage margin, and CBAR live exchange rates.
  - **User & Multi-FIN Directory (`/admin/users`)**: Searchable user management with slide-in FIN drawer, monthly $300 DGK quota progress, and status controls.
  - **Master Logistics Grid (`/admin/orders`)**: Cross-carrier, cross-platform global parcel monitoring.
  - **DGK SmartCustoms Supervisor (`/admin/customs`)**: Pre-declaration review queue, $250+ risk flags, liquid/drone restriction badges, and modal for manual HS code / category override.
  - **Carrier Margins & Arbitrage Matrix (`/admin/carriers`)**: Live base rates, platform markup percentages, active branch counts, and latency metrics.
  - **Immutable Security Audit Stream (`/admin/audit`)**: Real-time event stream logging auth attempts, quota threshold alerts, and compliance actions.

---

## [4.0.0] - 2026-10-16

### 🚀 Major Release: Autonomous Multi-Carrier Logistics & Customs Copilot

KargoPilot v4.0 is a generational leap from the single-carrier v3.5 architecture to a full-fledged autonomous multi-carrier orchestration suite, customs compliance copilot, and AI-driven shopper assistant for Azerbaijan's cross-border Silk Road trade (Taobao, 1688, Trendyol, Temu, and Amazon).

### ✨ Added
- **Multi-Carrier Arbitrage Engine (`CrossPlatformArbitrageEngine`)**:
  - Live price and tariff calculation across Azerbaijan's top freight forwarders: **Starex**, **Limak**, **Camex**, and **Dynamex** (with support for Mover, Colibri, and ASE).
  - Volumetric weight pricing engine ($L \times W \times H / 6000$) versus physical weight arbitrage.
  - Real-time currency conversion using official Central Bank of Azerbaijan (CBAR) exchange rates (USD/AZN, TRY/AZN, CNY/AZN, EUR/AZN).
  - "Total Landed Cost in Baku" formula: Product Price + Domestic Origin Shipping + Air Freight + Customs Tariffs - Bank Cashback.
- **State Customs Committee (DGK) $300 USD Quota Shield & Family Mesh (`FamilyFinMeshOrchestrator`)**:
  - Real-time personal monthly duty-free import tracking against the legal $300 USD rolling limit.
  - Same-flight customs collision prevention algorithm: alerts when multiple orders arrive on the same airway manifest, preventing forced commercial reclassification.
  - Multi-profile legal family allocation to distribute duty-free quotas across family FIN codes.
- **SmartCustoms RegTech & Invoice Preparation (`SmartCustomsBridge`)**:
  - Zero-shot mapping of raw Turkish and Chinese item descriptions into the 37 official legal DGK customs categories.
  - PDF Commercial Invoice Generator (ReportLab) producing formatted customs-compliant invoices with seller, tracking, HS codes, and recipient FIN.
- **1-Click Checkout Autofill (Chrome Extension MV3 + Floating HUD Bookmarklet)**:
  - Universal address injector for Trendyol, Taobao, 1688, Temu, and Amazon.
- **Dual-Tier Corporate Brand Identity**:
  - **Logo 6 (Infinity Parcel & Jet Loop)**: Primary brand identity for official web portal, GitHub repository, and documentation.
  - **Logo 5 (Silk Road Quantum 'K' Node)**: AI engine emblem for WhatsApp Loyd Copilot, Chrome Extension icon, and neural decision engine.

---

## [3.5.0] - 2026-10-15

### 📦 Baseline Release: Single-Carrier Pipeline & Early Customs Engine
- Basic parcel tracking for Starex.
- Elementary $300 limit warning based on static manual input.
- Prototype web panel with preliminary system monitoring and mock order views.
- Initial WhatsApp webhook receiver for status query notifications.
