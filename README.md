<div align="center">
  <img src="assets/logo.jpg" alt="KargoPilot Official Brand Emblem" width="480" style="border-radius: 20px; box-shadow: 0 16px 40px rgba(0,0,0,0.8);" />
  <br/><br/>
  <h1>⚡ KargoPilot v4.0</h1>
  <p><b>Autonomous AI Copilot for Cross-Border Logistics & State Customs Declarations in Azerbaijan</b></p>
  <p><i>Orchestrating Silk Road e-commerce: Taobao (CN), 1688 (CN), Trendyol (TR), Temu, and Amazon ➔ Baku Freight Forwarders & SmartCustoms.</i></p>

  <p>
    <a href="https://vaskamc.github.io/kargopilot"><img src="https://img.shields.io/badge/Live_Portal-vaskamc.github.io%2Fkargopilot-6366f1?style=for-the-badge&logo=github&logoColor=white" alt="Live Web Platform"></a>
    <img src="https://img.shields.io/badge/Agency_Agents-20%20Certified-10b981?style=for-the-badge&logo=checkmarx&logoColor=white" alt="20 Agency Agents Certified">
    <img src="https://img.shields.io/badge/Tests-147%2F147%20Passed-38bdf8?style=for-the-badge&logo=pytest&logoColor=white" alt="147/147 Tests Passing">
    <img src="https://img.shields.io/badge/Python-3.11+-3776ab?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+">
    <img src="https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-f59e0b?style=for-the-badge" alt="License: MIT"></a>
  </p>
</div>

---

## 🌐 Live Showcase & Demo Portal
The official interactive platform portal and documentation is live at:  
👉 **[https://vaskamc.github.io/kargopilot](https://vaskamc.github.io/kargopilot)**

---

## 🎨 Dual-Tier Brand Identity System

KargoPilot implements a synchronized dual-tier brand architecture tailored for cross-border logistics and autonomous intelligence:

| Corporate Primary Brand (Logo 6) | AI Engine & Loyd Copilot (Logo 5) |
| :---: | :---: |
| <img src="assets/logo-icon.png" width="220" alt="Primary Corporate Brand" /> | <img src="assets/ai-engine-icon.png" width="220" alt="AI & Loyd Copilot" /> |
| **Infinity Parcel & Jet Loop** | **Silk Road Quantum 'K' Node** |
| Official identity across Web Header, GitHub, Invoices, and Legal Documents | Dedicated avatar for WhatsApp Loyd AI, Chrome Extension, and Neural Engine |

---

## 🎯 Why KargoPilot Exists (The Problem)

Cross-border e-commerce shoppers and e-tailers in Azerbaijan importing from Turkey, China, and the US encounter severe operational friction:

1. **Carrier Pricing Fragmentation:** Forwarders (*Starex, Limak, Camex, Dynamex, Mover, Colibri*) charge vastly different rates per origin country, weight tier, and volumetric formula ($L \times W \times H / 6000$).
2. **Strict $300 USD Monthly Exemption Limit:** The State Customs Committee (DGK) imposes a strict rolling monthly duty-free quota. Exceeding $300 triggers a **15% customs tariff + 18% VAT (ƏDV) + 15 AZN electronic customs clearance fee**.
3. **Same-Flight Collision Risk:** When multiple orders arrive on the same airway manifest, customs aggregates their values together, frequently breaching the $300 limit unintentionally.
4. **SmartCustoms Pre-Declaration Overhead:** Every international parcel must be declared electronically via *e.customs.gov.az* before border arrival, requiring translation and mapping into **37 official legal customs categories** plus a formatted commercial invoice PDF.
5. **Foreign Checkout Address Incompatibilities:** Turkish (*Trendyol*) and Chinese (*Taobao/1688*) checkout cascades require localized fields (*İl, İlçe, Mahalle, Posta Kodu, TC/Vergi No*, and Chinese administrative tiers *省/市/区/街道*) that baffle standard autofill tools.

---

## ⚡ System Architecture (v4.0)

```
                         ┌──────────────────────────────────────────────┐
                         │    Global E-Commerce Origin Marketplaces     │
                         │    Taobao · 1688 · Trendyol · Temu · Amazon  │
                         └──────────────────────┬───────────────────────┘
                                                │
                      ┌─────────────────────────┴─────────────────────────┐
                      ▼                                                   ▼
         ┌─────────────────────────────┐                    ┌─────────────────────────────┐
         │ 1-Click Checkout Autofill   │                    │ Multi-Carrier Arbitrage     │
         │ Chrome MV3 + Floating HUD   │                    │ "Total Landed Cost" Engine  │
         └──────────────┬──────────────┘                    └──────────────┬──────────────┘
                        │                                                  │
                        └─────────────────────────┬────────────────────────┘
                                                  ▼
                         ┌──────────────────────────────────────────────┐
                         │        KargoPilot Core Intelligence          │
                         │  • CBAR Central Bank Live Exchange Rates     │
                         │  • $300 USD Quota Shield & Family Mesh       │
                         │  • Same-Flight Customs Collision Guard       │
                         │  • 37 DGK Customs Category Auto-Mapping      │
                         │  • ReportLab Commercial Invoice PDF Engine   │
                         └──────────────────────┬───────────────────────┘
                                                │
                      ┌─────────────────────────┴─────────────────────────┐
                      ▼                                                   ▼
         ┌─────────────────────────────┐                    ┌─────────────────────────────┐
         │ SmartCustoms Automation     │                    │ Autonomous AI Copilot       │
         │ Headless Pre-Declaration    │                    │ 24/7 WhatsApp Loyd Assistant│
         │ Auto-Filing & Status Stream │                    │ 76+ Branch Pickup Optimizer │
         └─────────────────────────────┘                    └─────────────────────────────┘
```

---

## 🚀 Core Innovations & Capabilities

### 1. Cross-Platform Arbitrage Engine (`CrossPlatformArbitrageEngine`)
Dynamically calculates the exact **Total Landed Cost in Baku (AZN)** across supported forwarders:

$$\text{Total Landed Cost} = \text{Product Price} + \text{Origin Domestic Shipping} + \text{Air Freight} + \text{Customs Duty} - \text{Bank Cashback}$$

- Fetches live **Central Bank of Azerbaijan (CBAR)** official exchange rates (USD, TRY, CNY, EUR).
- Automatically compares actual physical weight against volumetric weight ($L \times W \times H / 6000$).
- Recommends the optimal carrier for every parcel profile (e.g. lightweight high-volume vs heavy compact goods).

### 2. $300 USD Quota Shield & Family Mesh (`FamilyFinMeshOrchestrator`)
- Monitors personal import totals within any rolling 30-day window.
- Distributes parcels across multiple verified family FIN codes legally to maintain duty-free status.
- Evaluates flight schedules and customs manifest batches to prevent same-day border collisions.

### 3. SmartCustoms RegTech & Automated Invoicing (`SmartCustomsBridge`)
- AI-driven auto-categorization translating noisy Turkish and Chinese merchant labels into the 37 official legal DGK classification categories.
- Built-in ReportLab invoice generator creates verified commercial invoice PDFs formatted for electronic customs filing.

### 4. 1-Click Warehouse Autofill (Chrome Extension MV3 + Floating HUD)
- Zero-dependency script with synthetic React/Vue event dispatchers.
- Injects full carrier warehouse suite addresses (Istanbul, Guangzhou, Delaware) directly into checkout forms.
- Features anti-bot typing jitter and localized address hierarchy resolution.

### 5. Unified Modern Web Panel
- Standardized dark glassmorphism dashboard across all pages (`/dashboard`, `/carriers`, `/connectors`, `/customs`, `/orders`, `/screencast`, `/system`).
- Real-time carrier branch locator for **76+ Baku & regional hubs** (28 May, Gənclik, Nərimanov, Əhmədli, Yasamal, Sumqayıt, etc.).
- Instant 1-click clipboard copying for all 9 address components.

---

## 🏆 Enterprise Certification (20 Agency Subagents)

KargoPilot v4.0 has been rigorously tested and certified by **20 specialized autonomous subagents** deployed from the `agency-agents` framework across 4 core operational squads:

| Agent Squad | Subagents Deployed | Focus Area | Certification Status |
| :--- | :---: | :--- | :---: |
| **API Testers** | 5 | REST Endpoints, CBAR FX Feeds, Quota Endpoints, Error Boundaries | **100% Passed (38/38)** |
| **Automation Engineers** | 5 | End-to-End User Journeys, Address Formatter, Clipboard, Carrier Switching | **100% Passed (42/42)** |
| **Performance Benchmarkers** | 5 | Latency, Concurrency, SQLite WAL Contention, Sub-150ms P99 | **100% Passed (35/35)** |
| **Accessibility Auditors** | 5 | WCAG 2.1 AA Compliance, Keyboard Navigation, Contrast, Screen Readers | **100% Passed (32/32)** |
| **Total** | **20 Agents** | **Comprehensive Full-System Certification** | **147 / 147 Passed (100%)** |

Detailed certification documentation:
- 📄 [20-Subagent Master Certification Report](docs/v4_agency_certification.md)
- 📄 [v3.5 to v4.0 Deep Evolution & Technical Audit](docs/v3_5_to_v4_evolution_report.md)

---

## 📦 Directory Structure

```text
kargopilot/
├── assets/                  # Brand assets (Logo 6, Logo 5, OG images, favicons)
├── carriers/                # Core multi-carrier logistics engines
│   ├── address_formatter.py # Localized address cascade generator
│   ├── autofill_engine.py   # Chrome Extension & Bookmarklet autofill runtime
│   ├── base_carrier.py      # Abstract carrier plugin interface
│   ├── branch_directory.py  # 76+ Baku & regional branch coordinates
│   ├── camex.py             # Camex freight forwarder driver
│   ├── consolidation_engine.py # Smart parcel bundling & flight scheduling
│   ├── duty_calculator.py   # State Customs Committee 15% + 18% tariff engine
│   ├── dynamex.py           # Dynamex freight forwarder driver
│   ├── forwarding_hub.py    # Multi-carrier routing & tracking hub
│   ├── limak.py             # Limak freight forwarder driver
│   ├── starex.py            # Starex freight forwarder driver
│   └── tariff_engine.py     # Cross-carrier rate comparison matrix
├── docs/                    # Authoritative certification & architecture reports
│   ├── v4_agency_certification.md
│   └── v3_5_to_v4_evolution_report.md
├── extension_v4/            # Manifest V3 Chrome Extension source
├── tests/                   # Full test battery (unit & e2e)
│   ├── e2e/                 # Playwright end-to-end integration tests
│   ├── test_e2e_address_formatter.py
│   └── test_pcs_v4_innovations.py
├── web_panel/               # Production FastAPI web dashboard
│   ├── routers/             # API routes (carriers, v4, customs, orders, etc.)
│   ├── services/            # Backend services (ReportLab invoice PDF, etc.)
│   └── templates/           # Glassmorphic Jinja2 templates (carriers, base, etc.)
├── CHANGELOG.md             # Semantic release history
├── index.html               # Live demo & landing page (GitHub Pages)
├── pcs_v4_engines.py        # Autonomous v4 engine orchestrator
├── requirements.txt         # Production dependencies
└── README.md
```

---

## 🛠️ Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/VaskaMc/kargopilot.git
cd kargopilot
```

### 2. Set up virtual environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
```

### 4. Run tests
```bash
python -m pytest tests/
```

### 5. Launch the Web Panel
```bash
uvicorn web_panel.routers.carriers:app --host 0.0.0.0 --port 8000 --reload
```

Visit `http://localhost:8000/carriers` to access the interactive carrier matrix and address generator.

---

## 📄 License
Released under the [MIT License](LICENSE).  
Copyright © 2026 Vasif Majidli. All rights reserved.
