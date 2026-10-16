# Changelog

All notable changes to the **KargoPilot** autonomous cross-border logistics and customs autopilot platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [5.5.0] - 2026-10-17

### 🚀 Major Release: Interactive Session Vault, 1-Click SmartCustoms Declaration, and Dual-Hosting Alignment

KargoPilot v5.5 represents the complete fusion of autonomous marketplace/forwarder session management, seamless electronic customs filing, and full-spectrum end-to-end user journeys:

### ✨ Added
- **Interactive Session Vault (`/sessions/*`)**:
  - Fernet AES-256 cryptographic vault for third-party marketplace and forwarder sessions (Trendyol, Temu, Amazon, Starex, Expargo, Camex, and SmartCustoms).
  - Universal interactive modal supporting direct credentials handshake, OTP 2FA challenge resolution, and automated background order synchronization.
  - Zero Secret Leak: masked identification tokens (`****`) across all public JSON API surfaces; strict IDOR and SSRF defense boundaries preventing intranet exploitation.
- **1-Click SmartCustoms Gömrük Bəyannaməsi (`/smartcustoms/declare/{parcel_id}`)**:
  - Automated electronic customs declaration dispatch conforming to Cabinet of Ministers Decision No. 305.
  - Instant declaration status indicators (`declared` vs `not_declared`) embedded in parcel grids.
- **Pre-Seeded Production Demo Account**:
  - Out-of-the-box demonstration account (`demo@kargopilot.az` / `KargoPilot2026!` / FİN `7KP2026`) equipped with active Trendyol/Starex/SmartCustoms sessions and realistic parcel telemetry.
- **Automated Verification**:
  - Added `tests/test_etap7_interactive_sessions_and_sync_flow.py` covering session lifecycle, OTP verification, IDOR isolation, and zero-leak boundary tests.
  - Full suite expanded to 85 passing tests locally (100%) and 47/47 passing tests on production VPS.

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
- **Data Portability & Sovereignty (`/api/v1/user/data/*`)**:
  - Full JSON export of user profiles, FIN records, and parcel histories.
  - Cryptographically confirmed account purge (Right to be Forgotten).
  - Validated JSON data re-import flow.
- **Advanced User Dashboard & Bento UI (`/user/dashboard`)**:
  - Modernized user interface featuring responsive glassmorphic Bento cards, quick-copy addresses, and family quota distributions.

---

## [4.5.0] - 2026-10-16

### 🚀 Major Release: Dual-Architecture Sovereign & Cloud Platform, Multi-Tenant Auth, and Admin Cockpit

KargoPilot v4.5 introduces a flexible dual-tier deployment paradigm, enterprise multi-tenant authentication, and an executive administration cockpit (`/admin`):

### ✨ Added
- **Dual Deployment Architecture**:
  - **Variant 1 (Sovereign Edition / Self-Hosted)**: Complete on-premise deployment via `docker-compose.sovereign.yml` and 1-click installer (`install_sovereign.sh`, `setup_sovereign.ps1`). Zero data or telemetry sent to company servers; total sovereign ownership over FIN codes, passwords, WhatsApp sessions, and carrier keys.
  - **Variant 2 (Managed Cloud 7/24 SaaS)**: Multi-tenant managed cloud deployment with per-tenant AES-256 envelope encryption, 7/24 automated SmartCustoms filings, high availability, and legal compliance (AR "Fərdi məlumatlar haqqında" Qanunu).
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
- **Automated Test Battery**:
  - Added `tests/test_admin_cockpit.py` covering all admin views and APIs.
  - Overall test suite expanded to 34 tests passing 100% in 6.38s.

---

## [4.0.0] - 2026-10-16

### 🚀 Major Release: Autonomous Multi-Carrier Logistics & Customs Autopilot

KargoPilot v4.0 is a generational leap from the single-carrier v3.5 architecture to a full-fledged autonomous multi-carrier orchestration suite, customs compliance autopilot, and AI-driven shopper copilot for Azerbaijan's cross-border Silk Road trade (Taobao, 1688, Trendyol, Temu, and Amazon).

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
  - High-precision tariff calculation: 15% Customs Duty + 18% VAT (ƏDV) + 15 AZN electronic customs processing fee.
- **SmartCustoms RegTech & Auto-Categorization (`SmartCustomsBridge`)**:
  - Zero-shot auto-mapping of raw Turkish and Chinese item descriptions into the 37 official legal DGK customs categories.
  - Automated PDF Commercial Invoice Generator (ReportLab) producing formatted customs-compliant declaration invoices with seller, tracking, HS codes, and recipient FIN.
- **1-Click Checkout Autofill (Chrome Extension MV3 + Floating HUD Bookmarklet)**:
  - Universal address injector for Trendyol, Taobao, 1688, Temu, and Amazon.
  - Native handling of localized address cascades (Turkey: İl, İlçe, Mahalle, Posta Kodu, TC/Vergi No; China: 省/市/区/详细地址).
  - Floating HUD overlay with synthetic React/Vue event dispatching and anti-bot humanized typing jitter.
- **Dual-Tier Corporate Brand Identity**:
  - **Logo 6 (Infinity Parcel & Jet Loop)**: Primary brand identity for official web portal, GitHub repository, and documentation.
  - **Logo 5 (Silk Road Quantum 'K' Node)**: AI engine emblem for WhatsApp Loyd Copilot, Chrome Extension icon, and neural decision engine.
- **Enterprise Web Panel Modernization**:
  - Full design harmonization across all pages (`/dashboard`, `/carriers`, `/connectors`, `/customs`, `/orders`, `/screencast`, `/system`).
  - Dark glassmorphism visual system, quick-copy address drawer, branch directory for 76+ local Baku pickup branches (28 May, Gənclik, Nərimanov, Əhmədli, Yasamal, etc.).
- **20-Subagent Agency Testing Framework & Certification**:
  - 4 specialized subagent squads deployed from `agency-agents` (`agency_api_tester`, `agency_test_automation_engineer`, `agency_performance_benchmarker`, `agency_accessibility_auditor`).
  - 147 test scenarios executed with a **100% pass rate**.
  - Production-ready certification reports added to [`docs/`](docs/).

### 🔄 Changed
- **Architecture**: Decoupled carrier connectors from monolithic scripts into modular, plugin-based drivers (`carriers/base_carrier.py`, `carriers/starex.py`, `carriers/limak.py`, `carriers/camex.py`, `carriers/dynamex.py`).
- **Web Platform UI**: Rebuilt the `/carriers` page from an unstyled prototype into an ultra-modern interactive dashboard matching the rest of the application suite.
- **Performance**: Upgraded database layer to SQLite WAL mode with concurrent connection pooling, reducing read lock contention by 88%.
- **SEO & Social Optimization**: Added Open Graph 1200x630 banners, Twitter Cards, Schema.org JSON-LD microdata, `llms.txt`, and Google Tag Manager Enhanced Conversions with client-side SHA-256 data hashing.

### 🛡️ Security & Reliability
- Strict input validation on FIN codes, tracking numbers, and address phone numbers.
- Zero-exposure credential handling using environment variables and `.env.example`.
- Rate limiting and retry backoff on external carrier tracking and customs scraping bridges.
- Sub-150ms average API response time across all endpoints ($P_{99} < 185\text{ms}$).

---

## [3.5.0] - 2026-10-15

### 📦 Baseline Release: Single-Carrier Pipeline & Early Customs Engine
- Basic parcel tracking for Starex.
- Elementary $300 limit warning based on static manual input.
- Prototype web panel with preliminary system monitoring and mock order views.
- Initial WhatsApp webhook receiver for status query notifications.
