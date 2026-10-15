# ⚡ KargoPilot

> **Autonomous AI Copilot for Cross-Border Logistics & State Customs Declarations in Azerbaijan**  
> Streamlining Silk Road e-commerce: Taobao (CN), 1688 (CN), Trendyol (TR), Temu, and Amazon ➔ Baku Freight Forwarders & SmartCustoms.

[![Live Web Platform](https://img.shields.io/badge/Live_Site-vaskamc.github.io%2Fkargopilot-indigo?style=for-the-badge&logo=github)](https://vaskamc.github.io/kargopilot)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg?style=for-the-badge&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald.svg?style=for-the-badge)](LICENSE)
[![Tests Passing](https://img.shields.io/badge/Tests-147%20Passed-brightgreen.svg?style=for-the-badge)](tests/)

---

## 🌐 Live Showcase & Demo
The live platform documentation and visual portal is deployed at:  
👉 **[https://vaskamc.github.io/kargopilot](https://vaskamc.github.io/kargopilot)**

---

## 🎯 Key Problems Solved

Cross-border shoppers and businesses in Azerbaijan importing goods face complex friction:
1. **Multi-Carrier Price Discrepancies:** Freight forwarders (*Starex, Limak, Camex, Dynamex*) charge varying rates per country, weight tier, and volumetric dimensions ($L \times W \times H / 6000$).
2. **Monthly Duty-Free Customs Threshold ($300 USD Allowance):** The State Customs Committee (DGK) imposes strict monthly quotas. Exceeding $300 triggers a 15% tariff + 18% VAT (ƏDV) + 15 AZN electronic customs clearance fee.
3. **SmartCustoms Pre-Declaration Friction:** Every international parcel must be declared with a commercial invoice and classified into one of 37 official customs categories before arriving at the border.
4. **Checkout Form Incompatibilities:** Turkish (*Trendyol*) and Chinese (*Taobao/1688*) address fields require specific formatting (İl, İlçe, Mahalle, TC/Vergi No, 省/市/区 cascade) that differ from local formats.

---

## ⚡ Core Capabilities (v4.0 Architecture)

```
                         ┌─────────────────────────────────────────┐
                         │   Global E-Commerce Origin Marketplaces │
                         │   Taobao · 1688 · Trendyol · Temu · Amazon│
                         └────────────────────┬────────────────────┘
                                              │
                     ┌────────────────────────┴────────────────────────┐
                     ▼                                                 ▼
        ┌───────────────────────────┐                    ┌───────────────────────────┐
        │ 1-Click Checkout Autofill │                    │ Cross-Platform Arbitrage  │
        │  Chrome MV3 live overlay  │                    │  "Total Landed Cost" AI   │
        └────────────┬──────────────┘                    └─────────────┬─────────────┘
                     │                                                 │
                     └────────────────────────┬────────────────────────┘
                                              ▼
                         ┌─────────────────────────────────────────┐
                         │       KargoPilot Intelligence Engine    │
                         │  • Rate Arbitrage (Starex, Camex, etc.) │
                         │  • $300 USD Quota Shield & Splitter     │
                         │  • Hazmat / IMEI / Restriction Guardian │
                         │  • 37 DGK Customs Category Auto-Mapping │
                         └────────────────────┬────────────────────┘
                                              │
                     ┌────────────────────────┴────────────────────────┐
                     ▼                                                 ▼
        ┌───────────────────────────┐                    ┌───────────────────────────┐
        │   SmartCustoms Automation │                    │  Multi-Channel AI Copilot │
        │ Headless Pre-Declaration  │                    │ WhatsApp Loyd 24/7 Agent  │
        │ Invoice PDF Generation    │                    │ Live Tracking & QR Pickup │
        └───────────────────────────┘                    └───────────────────────────┘
```

### 1. Cross-Platform Arbitrage Engine (`CrossPlatformArbitrageEngine`)
Calculates the **Total Landed Cost in Baku (AZN)** across platforms:
$$\text{Landed Cost} = \text{Product Price} + \text{Local Shipping} + \text{Air Freight} + \text{Customs Duty} - \text{Bank Cashback}$$

### 2. $300 USD Quota Guard & Family Mesh (`FamilyFinMeshOrchestrator`)
* Tracks monthly personal imports in real-time using official Central Bank of Azerbaijan (CBAR) exchange rates.
* Detects same-flight customs collision risks when multiple packages arrive simultaneously.
* Balances parcel allocation across family accounts to optimize duty-free allowances legally.

### 3. SmartCustoms RegTech & Auto-Categorization
* Translates noisy Chinese and Turkish product descriptions into one of the 37 official legal DGK classification categories with zero-shot accuracy.
* Auto-generates standard international commercial invoices (PDF) formatted for electronic customs filing.

### 4. 1-Click Warehouse Autofill (Chrome Extension MV3)
* Injects verified foreign warehouse suite addresses (Istanbul, Guangzhou, Delaware) into checkout fields with a single click.

### 5. Multi-Carrier Rate & Pickup Optimizer
* Compares real-time freight rates across **Starex**, **Limak**, **Camex**, and **Dynamex**.
* Maps pickup orders to **76+ local branch locations** (28 May, Gənclik, Nərimanov, Əhmədli, Elmlər, etc.) with walking distance optimization.

---

## 🛠️ Tech Stack

* **Backend:** Python 3.11+, FastAPI, SQLAlchemy, SQLite (WAL mode, high concurrency).
* **Automation:** Playwright, Chrome DevTools Protocol (CDP).
* **Browser Extension:** Manifest V3 (Chrome, Edge, Brave).
* **AI & Vision:** Multimodal Vision OCR for receipts and airway bills.
* **Integrations:** Starex, Limak, Camex, Dynamex, SmartCustoms (e.customs.gov.az).

---

## 🚀 Quick Start (Local Development)

### 1. Clone the repository
```bash
git clone https://github.com/VaskaMc/kargopilot.git
cd kargopilot
```

### 2. Set up environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure credentials
Copy the example configuration:
```bash
cp .env.example .env
```
Edit `.env` with your desired configuration (demo values provided out of the box).

### 4. Run tests
```bash
pytest -v
```

---

## 📄 License
Released under the [MIT License](LICENSE). Copyright © 2026 Vasif Majidli.
