"""ForwardingHub: Zero-Touch Pre-Declaration, Triple-Link Engine, and !kargo WhatsApp Reporter."""



from __future__ import annotations



import json

import sqlite3

import uuid

from datetime import datetime, timezone

from pathlib import Path

from typing import Any, Callable, Coroutine, Dict, List, Optional



import httpx



from app.carriers import CarrierRegistry

from carriers.base_carrier import (

    CarrierAccountDTO,

    CarrierShipmentDTO,

    PreDeclarationRequest,

    ShipmentStatus,

)

from carriers.tariff_calculator import calculate_delivery_fee

from app.currency import CurrencyConverter

from app.customs_engine.categorizer import classify_dgk_category





HUB_CITY_NAMES = {

    ("STAREX", "CN"): "Quançjou",

    ("STAREX", "TR"): "İstanbul (Avcılar)",

    ("LIMAK", "TR"): "İstanbul (Halkalı)",

    ("LIMAK", "CN"): "Quançjou",

    ("CAMEX", "CN"): "Quançjou / Yiwu",

    ("DYNAMEX", "TR"): "İstanbul",

}





def generate_minimal_invoice_pdf(

    order_ref: str,

    platform: str,

    seller_name: str,

    origin_tracking: str,

    item_title: str,

    dgk_cat: str,

    quantity: int,

    amount: float,

    currency: str,

    amount_azn: float,

    amount_usd: float,

    invoices_dir: Path,

) -> Path:

    """Generates a valid PDF-1.4 Commercial Invoice document at /data/pcs/invoices/{order_ref}_customs_invoice.pdf."""

    invoices_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = invoices_dir / f"{order_ref}_customs_invoice.pdf"

    text_lines = [

        f"COMMERCIAL INVOICE - {platform.upper()}",

        f"Order Ref: {order_ref} | Seller: {seller_name}",

        f"Origin Tracking: {origin_tracking} | DGK Category: {dgk_cat}",

        f"Item: {item_title} (Qty: {quantity})",

        f"Original Total: {amount:.2f} {currency} | AZN: {amount_azn:.2f} AZN | Customs USD: {amount_usd:.2f} USD",

    ]

    body_stream = "BT /F1 11 Tf 40 760 Td 16 TL " + " ".join(

        f"({line.replace('(', '[').replace(')', ']')}) Tj T*" for line in text_lines

    ) + " ET"

    pdf_bytes = (

        "%PDF-1.4\n"

        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"

        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"

        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "

        "/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >> endobj\n"

        f"4 0 obj << /Length {len(body_stream)} >> stream\n{body_stream}\nendstream endobj\n"

        "xref\n0 5\n0000000000 65535 f \n"

        "trailer << /Root 1 0 R /Size 5 >>\n%%EOF\n"

    ).encode("utf-8")

    pdf_path.write_bytes(pdf_bytes)

    return pdf_path





class ForwardingHub:

    """Orchestrates Zero-Touch Pre-Declaration, Triple-Link AWB resolution, and WhatsApp alerts."""



    def __init__(

        self,

        db_path: Path,

        invoices_dir: Path,

        transport_map: Optional[Dict[str, httpx.AsyncBaseTransport]] = None,

        whatsapp_notifier: Optional[Callable[[str], Coroutine[Any, Any, None]]] = None,

    ) -> None:

        self.db_path = Path(db_path)

        self.invoices_dir = Path(invoices_dir)

        self.transport_map = transport_map or {}

        self.whatsapp_notifier = whatsapp_notifier



    def _connect(self) -> sqlite3.Connection:

        conn = sqlite3.connect(str(self.db_path), timeout=30.0)

        conn.row_factory = sqlite3.Row

        conn.execute("PRAGMA journal_mode=WAL;")

        conn.execute("PRAGMA busy_timeout=30000;")

        return conn



    def upsert_carrier_account(self, account: CarrierAccountDTO) -> str:

        acc_id = account.id or uuid.uuid4().hex

        now_iso = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:

            existing = conn.execute(

                "SELECT id FROM carrier_accounts WHERE UPPER(carrier_name) = ?",

                (account.carrier_name.upper(),),

            ).fetchone()

            if existing:

                acc_id = existing["id"]

                conn.execute(

                    """UPDATE carrier_accounts

                       SET customer_code=?, email=?, auth_token=?, is_active=?,

                           default_branch=?, warehouse_suites=?, last_sync_at=?

                       WHERE id=?""",

                    (

                        account.customer_id,

                        account.email,

                        account.auth_token,

                        1 if account.is_active else 0,

                        account.default_branch,

                        json.dumps(account.warehouse_suites, ensure_ascii=False),

                        now_iso,

                        acc_id,

                    ),

                )

            else:

                conn.execute(

                    """INSERT INTO carrier_accounts

                       (id, carrier_name, customer_code, email, auth_token, is_active, default_branch, warehouse_suites, last_sync_at)

                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",

                    (

                        acc_id,

                        account.carrier_name.upper(),

                        account.customer_id,

                        account.email,

                        account.auth_token,

                        1 if account.is_active else 0,

                        account.default_branch,

                        json.dumps(account.warehouse_suites, ensure_ascii=False),

                        now_iso,

                    ),

                )

            conn.commit()

        return acc_id



    def list_accounts(self) -> List[CarrierAccountDTO]:

        with self._connect() as conn:

            rows = conn.execute("SELECT * FROM carrier_accounts ORDER BY carrier_name ASC").fetchall()

            result: List[CarrierAccountDTO] = []

            for r in rows:

                suites = json.loads(r["warehouse_suites"]) if r["warehouse_suites"] else {}

                result.append(

                    CarrierAccountDTO(

                        id=r["id"],

                        carrier_name=r["carrier_name"],

                        customer_id=r["customer_code"],

                        auth_token=r["auth_token"],

                        email=r["email"],

                        default_branch=r["default_branch"] or "28 May",

                        is_active=bool(r["is_active"]),

                        warehouse_suites=suites,

                    )

                )

            return result



    async def auto_pre_declare(

        self,

        carrier_name: str,

        order_ref: str,

        platform: str,

        origin_country: str,

        origin_tracking: str,

        seller_name: str,

        item_title: str,

        quantity: int,

        invoice_amount: float,

        invoice_currency: str,

        branch_id: str = "28 May",

    ) -> Dict[str, Any]:

        """Step 1-4 of Zero-Touch Workflow: Classify -> Generate PDF Invoice -> Submit Pre-Declaration -> Persist."""

        dgk_cat = classify_dgk_category(item_title)

        amount_azn, amount_usd = CurrencyConverter.convert_pair(invoice_amount, invoice_currency)



        pdf_path = generate_minimal_invoice_pdf(

            order_ref=order_ref,

            platform=platform,

            seller_name=seller_name,

            origin_tracking=origin_tracking,

            item_title=item_title,

            dgk_cat=dgk_cat,

            quantity=quantity,

            amount=invoice_amount,

            currency=invoice_currency,

            amount_azn=amount_azn,

            amount_usd=amount_usd,

            invoices_dir=self.invoices_dir,

        )



        # Ensure parent order exists in orders table so FK is satisfied

        now_iso = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:

            ord_row = conn.execute(

                "SELECT id FROM orders WHERE temu_order_ref = ?", (order_ref,)

            ).fetchone()

            if not ord_row:

                conn.execute(

                    """INSERT INTO orders

                       (id, temu_order_ref, tracking_number, carrier, receiver_name, receiver_phone,

                        temu_invoice_amount, temu_invoice_currency, invoice_amount_azn, status, extra, created_at, updated_at)

                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",

                    (

                        uuid.uuid4().hex,

                        order_ref,

                        origin_tracking,

                        carrier_name.upper(),

                        "Vasif Majidli",

                        "994501234567",

                        invoice_amount,

                        invoice_currency.upper(),

                        amount_azn,

                        "STORED",

                        json.dumps({"platform": platform, "origin_tracking": origin_tracking}),

                        now_iso,

                        now_iso,

                    ),

                )

            conn.commit()



        # Resolve carrier account

        accounts = [a for a in self.list_accounts() if a.carrier_name.upper() == carrier_name.upper() and a.is_active]

        if accounts:

            account = accounts[0]

        else:

            account = CarrierAccountDTO(

                carrier_name=carrier_name.upper(),

                customer_id=f"{carrier_name[:2].upper()}-DEFAULT",

                auth_token="live-session-token",

                default_branch=branch_id,

            )



        transport = self.transport_map.get(carrier_name.upper())

        adapter = CarrierRegistry.create(account=account, transport=transport)



        req = PreDeclarationRequest(

            order_ref=order_ref,

            platform=platform,

            origin_country=origin_country.upper(),

            origin_tracking=origin_tracking,

            seller_name=seller_name,

            dgk_main_cat=dgk_cat,

            item_title=item_title,

            quantity=quantity,

            invoice_amount=invoice_amount,

            invoice_currency=invoice_currency.upper(),

            invoice_pdf_path=pdf_path,

            branch_id=branch_id,

        )

        api_res = await adapter.submit_pre_declaration(req)

        dest_trk = api_res.get("destination_tracking")



        shipment_id = uuid.uuid4().hex

        with self._connect() as conn:

            existing_sh = conn.execute(

                "SELECT id FROM carrier_shipments WHERE origin_tracking = ?",

                (origin_tracking,),

            ).fetchone()

            if existing_sh:

                shipment_id = existing_sh["id"]

                conn.execute(

                    """UPDATE carrier_shipments

                       SET carrier_name=?, order_ref=?, destination_tracking=COALESCE(?, destination_tracking),

                           origin_country=?, seller_name=?, declared_amount=?, declared_currency=?,

                           amount_azn=?, amount_usd=?, invoice_pdf_path=?, extra=?

                       WHERE id=?""",

                    (

                        carrier_name.upper(),

                        order_ref,

                        dest_trk,

                        origin_country.upper(),

                        seller_name,

                        invoice_amount,

                        invoice_currency.upper(),

                        amount_azn,

                        amount_usd,

                        str(pdf_path),

                        json.dumps({"dgk_main_cat": dgk_cat, "platform": platform, "item_title": item_title}, ensure_ascii=False),

                        shipment_id,

                    ),

                )

            else:

                conn.execute(

                    """INSERT INTO carrier_shipments

                       (id, carrier_name, order_ref, origin_tracking, destination_tracking,

                        origin_country, seller_name, declared_amount, declared_currency,

                        amount_azn, amount_usd, status, invoice_pdf_path, pre_declared_at, extra)

                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",

                    (

                        shipment_id,

                        carrier_name.upper(),

                        order_ref,

                        origin_tracking,

                        dest_trk,

                        origin_country.upper(),

                        seller_name,

                        invoice_amount,

                        invoice_currency.upper(),

                        amount_azn,

                        amount_usd,

                        ShipmentStatus.PRE_DECLARED.value,

                        str(pdf_path),

                        now_iso,

                        json.dumps({"dgk_main_cat": dgk_cat, "platform": platform, "item_title": item_title}, ensure_ascii=False),

                    ),

                )

            conn.commit()



        return {

            "shipment_id": shipment_id,

            "order_ref": order_ref,

            "carrier": carrier_name.upper(),

            "origin_tracking": origin_tracking,

            "destination_tracking": dest_trk,

            "dgk_main_cat": dgk_cat,

            "amount_azn": amount_azn,

            "amount_usd": amount_usd,

            "invoice_pdf_path": str(pdf_path),

            "status": ShipmentStatus.PRE_DECLARED.value,

        }



    async def sync_all_carriers(self) -> Dict[str, Any]:

        """Step 5-7 of Zero-Touch Workflow: Poll carriers, bind AWB + SmartCustoms No, and dispatch WhatsApp alerts."""

        accounts = [a for a in self.list_accounts() if a.is_active]

        updated_count = 0

        notifications: List[str] = []

        now_iso = datetime.now(timezone.utc).isoformat()



        for account in accounts:

            transport = self.transport_map.get(account.carrier_name.upper())

            adapter = CarrierRegistry.create(account=account, transport=transport)

            remote_shipments = await adapter.fetch_active_shipments()



            with self._connect() as conn:

                for rem in remote_shipments:

                    row = conn.execute(

                        "SELECT * FROM carrier_shipments WHERE origin_tracking = ? OR (order_ref = ? AND order_ref != '')",

                        (rem.origin_tracking, rem.order_ref),

                    ).fetchone()

                    if not row:

                        continue



                    prev_dest = row["destination_tracking"]

                    prev_status = row["status"]

                    new_dest = rem.destination_tracking or prev_dest

                    new_status = rem.status or prev_status



                    # Check if SmartCustoms already has a declaration matching new_dest

                    sc_no = rem.smart_customs_no or row["smart_customs_no"]

                    if new_dest and not sc_no:

                        decl_row = conn.execute(

                            """SELECT cd.customs_ref FROM customs_declarations cd

                               JOIN orders o ON o.id = cd.order_id

                               WHERE o.tracking_number = ? OR o.temu_order_ref = ?""",

                            (new_dest, row["order_ref"]),

                        ).fetchone()

                        if decl_row and decl_row["customs_ref"]:

                            sc_no = decl_row["customs_ref"]



                    arrived_hub_at = row["arrived_hub_at"]

                    if new_status in (ShipmentStatus.AT_FOREIGN_HUB.value, ShipmentStatus.ON_THE_WAY.value) and not arrived_hub_at:

                        arrived_hub_at = now_iso



                    conn.execute(

                        """UPDATE carrier_shipments

                           SET destination_tracking=?, smart_customs_no=?, status=?,

                               weight_kg=COALESCE(?, weight_kg),

                               delivery_fee_usd=COALESCE(?, delivery_fee_usd),

                               delivery_fee_azn=COALESCE(?, delivery_fee_azn),

                               arrived_hub_at=?

                           WHERE id=?""",

                        (

                            new_dest,

                            sc_no,

                            new_status,

                            rem.weight_kg,

                            rem.delivery_fee_usd,

                            rem.delivery_fee_azn,

                            arrived_hub_at,

                            row["id"],

                        ),

                    )



                    # Triple-Link: Update orders.tracking_number with international AWB (STRAZ... / LMX...)

                    if new_dest:

                        conn.execute(

                            "UPDATE orders SET tracking_number=?, carrier=?, updated_at=? WHERE temu_order_ref=?",

                            (new_dest, account.carrier_name.upper(), now_iso, row["order_ref"]),

                        )



                    updated_count += 1



                    # Trigger WhatsApp notification when AWB is newly assigned at foreign warehouse

                    if new_dest and (not prev_dest or prev_status == ShipmentStatus.PRE_DECLARED.value):

                        extra_meta = json.loads(row["extra"]) if row["extra"] else {}

                        platform_label = extra_meta.get("platform") or ("Taobao" if row["order_ref"].startswith("TB") else "Trendyol")

                        hub_city = HUB_CITY_NAMES.get((account.carrier_name.upper(), row["origin_country"]), "xarici")

                        msg = (

                            f"📦 {account.carrier_name.title()}: {platform_label} sifarişiniz "

                            f"({row['order_ref']}) {hub_city} anbarına daxil oldu! "

                            f"Yeni AWB: {new_dest}. SmartCustoms bəyannaməsi avtomatik əlaqələndirildi."

                        )

                        notifications.append(msg)

                        if self.whatsapp_notifier:

                            await self.whatsapp_notifier(msg)



                conn.execute(

                    "UPDATE carrier_accounts SET last_sync_at=? WHERE id=?",

                    (now_iso, account.id),

                )

                conn.commit()



        return {

            "synced_carriers": len(accounts),

            "updated_shipments": updated_count,

            "notifications": notifications,

        }



    def list_shipments(self) -> List[Dict[str, Any]]:

        with self._connect() as conn:

            rows = conn.execute(

                "SELECT * FROM carrier_shipments ORDER BY created_at DESC"

            ).fetchall()

            out: List[Dict[str, Any]] = []

            for r in rows:

                d = dict(r)

                d["extra"] = json.loads(r["extra"]) if r["extra"] else {}

                out.append(d)

            return out



    def format_whatsapp_kargo_report(self) -> str:

        """Generates the consolidated !kargo WhatsApp telemetry message."""

        shipments = self.list_shipments()

        if not shipments:

            return "📦 Hazırda aktiv kargo bağlaması yoxdur."

        lines = [f"📦 *PCS v3.0 — Aktiv Kargo Bağlamaları ({len(shipments)} ədəd):*\n"]

        for idx, sh in enumerate(shipments, start=1):

            awb = sh.get("destination_tracking") or "Hələ təyin edilməyib"

            sc = f" | DGK: {sh['smart_customs_no']}" if sh.get("smart_customs_no") else ""

            fee = f" | Çatdırılma: {sh['delivery_fee_azn']:.2f} AZN" if sh.get("delivery_fee_azn") else ""

            lines.append(

                f"{idx}. *{sh['carrier_name']}* ({sh['origin_country']}) — `{sh['order_ref']}`\n"

                f"   • Daxili: `{sh['origin_tracking']}` ➔ AWB: `{awb}`\n"

                f"   • Status: *{sh['status']}* | Dəyər: ${sh.get('amount_usd') or 0:.2f} USD{fee}{sc}"

            )

        return "\n".join(lines)
