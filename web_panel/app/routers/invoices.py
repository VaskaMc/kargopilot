"""Commercial Invoice Generator & Downloader Router."""

from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

from app.services.invoice_engine import build_invoice_data, render_invoice_html, generate_invoice_pdf

router = APIRouter(prefix="/invoices")


@router.get("/{order_id}", response_class=HTMLResponse)
async def view_invoice_html(order_id: str):
    """Renders the DGK-compliant commercial invoice in printable HTML format."""
    data = build_invoice_data(order_id)
    if not data:
        raise HTTPException(status_code=404, detail="Sifariş tapılmadı")
    html = render_invoice_html(data)
    return HTMLResponse(content=html)


@router.get("/{order_id}/pdf")
async def download_invoice_pdf(order_id: str):
    """Generates and downloads the official commercial invoice PDF."""
    pdf_path = await generate_invoice_pdf(order_id)
    if not pdf_path or not pdf_path.exists():
        raise HTTPException(status_code=500, detail="İnvoys PDF faylı tərtib edilə bilmədi")

    media_type = "application/pdf" if pdf_path.suffix == ".pdf" else "text/html"
    return FileResponse(
        path=str(pdf_path),
        filename=pdf_path.name,
        media_type=media_type,
    )
