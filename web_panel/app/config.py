"""Configuration settings for Personal Customs System (PCS) Web Management Panel."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Server Binding - STRICT LOCALHOST BINDING (Security Requirement)
HOST: str = "127.0.0.1"
PORT: int = 48481

# Database Configuration
DB_PATH: Path = Path("/data/pcs/pcs.db")

# Log Configuration
PROD_LOG_PATH = Path("/data/pcs/logs/pcs.log")
LOCAL_LOG_PATH = BASE_DIR / "pcs.log"
LOG_PATH: Path = PROD_LOG_PATH if PROD_LOG_PATH.exists() else LOCAL_LOG_PATH

# Invoices Directory
INVOICE_DIR: Path = Path("/data/pcs/invoices")
try:
    INVOICE_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

# Screenshots Directory
SCREENSHOTS_DIR: Path = BASE_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Upstream PCS Worker API (FastAPI backend running locally on port 8088)
WORKER_API_URL: str = os.getenv("PCS_WORKER_URL", "http://127.0.0.1:8088")

# Customs & Financial Rules (Azerbaijan State Customs Committee - DGK)
# Decree No. 305: 300 USD duty-free threshold per calendar month
MONTHLY_CUSTOMS_QUOTA_USD: float = 300.0

# Central Bank of Azerbaijan (CBAR) Official Exchange Rates
USD_AZN_RATE: float = 1.7000  # Pegged rate
TRY_AZN_RATE: float = 0.0485  # Turkish Lira
CNY_AZN_RATE: float = 0.2380  # Chinese Yuan

# Consignee Details (Default Account Holder)
CONSIGNEE_NAME: str = "Vasif Məcidli"
CONSIGNEE_PHONE: str = "+994776346310"
CONSIGNEE_FIN: str = "6XXXXXX"
CONSIGNEE_ADDRESS: str = "Nəsimi rayonu, Eldar Tağızadə 1 (City Global Co-working Mərkəzi), Bakı, AZ1014"

# Secret Key for Sessions / CSRF
SECRET_KEY: str = os.getenv("PCS_SECRET_KEY", "pcs-secret-admin-key-48481-local")

settings = sys.modules[__name__]

