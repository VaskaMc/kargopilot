"""Main application factory for KargoPilot v4.0 (PCS) Central Web Panel."""

from __future__ import annotations

import hashlib
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, PlainTextResponse, Response, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.config import HOST, PORT, BASE_DIR
from app.database import init_db
from app.routers import (
    dashboard,
    orders,
    customs,
    connectors,
    screencast,
    invoices,
    system,
    api,
)

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s][%(name)s] %(message)s",
)
logger = logging.getLogger("pcs.web")

IMMUTABLE_EXTS = {".png", ".jpg", ".jpeg", ".ico", ".webp", ".svg", ".woff2"}
STATIC_DOC_EXTS = {".xml", ".txt", ".webmanifest", ".css", ".js"}
HTML_ROUTE_ALIASES = {
    "/index.html": "/",
    "/dashboard.html": "/",
    "/orders.html": "/orders",
    "/customs.html": "/customs",
    "/carriers.html": "/carriers",
    "/connectors.html": "/connectors",
    "/screencast.html": "/screencast",
    "/system.html": "/system",
    "/showcase.html": "/showcase",
    "/login.html": "/login",
    "/register.html": "/register",
    "/self-hosted.html": "/self-hosted",
    "/onboarding.html": "/self-hosted",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""
    logger.info("Initializing KargoPilot v6.5 Central Web Management Panel...")
    init_db()
    try:
        from app.carriers.forwarding_hub import ForwardingHub
        app.state.forwarding_hub = ForwardingHub(
            db_path=Path("/data/pcs/pcs.db"),
            invoices_dir=Path("/data/pcs/invoices"),
        )
        logger.info("ForwardingHub initialized on app.state")
    except Exception as exc:
        logger.warning("Could not initialize ForwardingHub on app.state: %s", exc)
    logger.info("KargoPilot Database verified and ready on %s:%d", HOST, PORT)
    yield
    logger.info("Shutting down KargoPilot Central Web Management Panel.")


def create_app() -> FastAPI:
    """Creates and configures the FastAPI instance."""
    app = FastAPI(
        title="KargoPilot v6.5 Enterprise Multi-Tenant Logistics & Customs AI",
        version="6.5.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def extension_and_cache_middleware(request: Request, call_next):
        """Normalizes .html extension links, supports HEAD on all GET routes, and enforces Cache-Control & ETag headers."""
        path = request.scope.get("path", "")
        if path in HTML_ROUTE_ALIASES:
            request.scope["path"] = HTML_ROUTE_ALIASES[path]
            path = request.scope["path"]

        is_head = request.scope.get("method") == "HEAD"
        if is_head and not (path.startswith("/static/") or path.startswith("/assets/") or path.startswith("/kargopilot/assets/")):
            request.scope["method"] = "GET"

        response = await call_next(request)
        lower_path = path.lower()
        ext = Path(lower_path).suffix

        if ext in IMMUTABLE_EXTS:
            response.headers["Cache-Control"] = "public, max-age=604800, immutable"
            response.headers["Vary"] = "Accept-Encoding"
        elif ext in STATIC_DOC_EXTS:
            response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"
            response.headers["Vary"] = "Accept-Encoding"
        elif ext == ".pdf":
            response.headers["Cache-Control"] = "private, max-age=3600"
        elif response.headers.get("content-type", "").startswith("text/html"):
            if path == "/showcase":
                response.headers["Cache-Control"] = "public, max-age=600, stale-while-revalidate=3600"
            else:
                response.headers["Cache-Control"] = "private, no-cache, must-revalidate"
            response.headers["Vary"] = "Accept-Encoding"

        if is_head and not (path.startswith("/static/") or path.startswith("/assets/") or path.startswith("/kargopilot/assets/")):
            return Response(content=b"", status_code=response.status_code, headers=dict(response.headers))

        return response

    # Static Files mounting
    static_dir = BASE_DIR / "app" / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    img_dir = BASE_DIR / "app" / "static" / "img"
    if img_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(img_dir)), name="assets")
        app.mount("/kargopilot/assets", StaticFiles(directory=str(img_dir)), name="kp_assets")

    ext_dir = BASE_DIR.parent / "extension_v4"
    if ext_dir.exists():
        app.mount("/extension_v4", StaticFiles(directory=str(ext_dir), html=True), name="extension_v4")

    # Include Routers
    app.include_router(dashboard.router)
    app.include_router(orders.router)
    app.include_router(customs.router)
    app.include_router(connectors.router)
    app.include_router(screencast.router)
    app.include_router(invoices.router)
    app.include_router(system.router)
    app.include_router(api.router)
    try:
        from app.routers import carriers as carriers_router
        app.include_router(carriers_router.router)
        logger.info("Mounted /carriers web management router")
    except Exception as exc:
        logger.warning("Could not mount /carriers router: %s", exc)

    try:
        from app.routers import v4 as v4_router
        app.include_router(v4_router.router)
        logger.info("Mounted /v4/api Omni-Commerce & Customs Intelligence v4.0 router")
    except Exception as exc:
        logger.warning("Could not mount /v4/api router: %s", exc)

    try:
        from app.routers import admin as admin_router
        app.include_router(admin_router.router)
        logger.info("Mounted /admin enterprise cockpit router")
    except Exception:
        try:
            from routers import admin as admin_router
            app.include_router(admin_router.router)
            logger.info("Mounted /admin enterprise cockpit router via fallback")
        except Exception as exc:
            logger.warning("Could not mount /admin router: %s", exc)

    try:
        from app.security.api_routes import router as auth_router
        app.include_router(auth_router)
        logger.info("Mounted /api/v1/auth multi-tenant authentication & WhatsApp security router")
    except Exception as exc:
        logger.warning("Could not mount auth router: %s", exc)

    try:
        from app.routers import auth_web as auth_web_router
        app.include_router(auth_web_router.router)
        logger.info("Mounted /login, /register, /user/dashboard web router")
    except Exception:
        try:
            from routers import auth_web as auth_web_router
            app.include_router(auth_web_router.router)
            logger.info("Mounted /login, /register, /user/dashboard web router via fallback")
        except Exception as exc:
            logger.warning("Could not mount auth_web router: %s", exc)

    try:
        from app.routers import user_api as user_api_router
        app.include_router(user_api_router.router)
        app.include_router(user_api_router.system_router)
        logger.info("Mounted /api/v1/user and /api/v1/system node verification & sovereignty routers")
    except Exception:
        try:
            from routers import user_api as user_api_router
            app.include_router(user_api_router.router)
            app.include_router(user_api_router.system_router)
            logger.info("Mounted /api/v1/user and /api/v1/system node verification & sovereignty routers via fallback")
        except Exception as exc:
            logger.warning("Could not mount user_api/system router: %s", exc)

    @app.get("/showcase", response_class=HTMLResponse)
    async def showcase_page():
        showcase_file = BASE_DIR / "app" / "templates" / "showcase.html"
        if showcase_file.exists():
            text = showcase_file.read_text(encoding="utf-8")
            etag = f'"{hashlib.md5(text.encode("utf-8")).hexdigest()}"'
            return HTMLResponse(content=text, headers={"ETag": etag})
        return HTMLResponse(content="Showcase page not found", status_code=404)

    @app.get("/robots.txt", response_class=PlainTextResponse)
    async def robots_txt():
        f = BASE_DIR / "app" / "static" / "robots.txt"
        content = f.read_text(encoding="utf-8") if f.exists() else "User-agent: *\nAllow: /\nSitemap: https://vaskamc.github.io/kargopilot/sitemap.xml\n"
        etag = f'"{hashlib.md5(content.encode("utf-8")).hexdigest()}"'
        return PlainTextResponse(content=content, headers={"ETag": etag})

    @app.get("/llms.txt", response_class=PlainTextResponse)
    async def llms_txt():
        f = BASE_DIR / "app" / "static" / "llms.txt"
        content = f.read_text(encoding="utf-8") if f.exists() else "# KargoPilot v4.0\n"
        etag = f'"{hashlib.md5(content.encode("utf-8")).hexdigest()}"'
        return PlainTextResponse(content=content, headers={"ETag": etag})

    @app.get("/sitemap.xml")
    async def sitemap_xml():
        f = BASE_DIR / "app" / "static" / "sitemap.xml"
        content = f.read_text(encoding="utf-8") if f.exists() else '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
        etag = f'"{hashlib.md5(content.encode("utf-8")).hexdigest()}"'
        return Response(content=content, media_type="application/xml; charset=utf-8", headers={"ETag": etag})

    @app.get("/site.webmanifest")
    async def site_webmanifest():
        f = BASE_DIR / "app" / "static" / "site.webmanifest"
        content = f.read_text(encoding="utf-8") if f.exists() else "{}"
        etag = f'"{hashlib.md5(content.encode("utf-8")).hexdigest()}"'
        return Response(content=content, media_type="application/manifest+json; charset=utf-8", headers={"ETag": etag})

    @app.get("/favicon.ico")
    async def root_favicon():
        ico = BASE_DIR / "app" / "static" / "img" / "favicon.ico"
        if ico.exists():
            return FileResponse(str(ico), media_type="image/x-icon")
        return Response(status_code=404)

    @app.get("/404.html", response_class=HTMLResponse)
    async def explicit_404_page():
        f = BASE_DIR / "app" / "templates" / "404.html"
        if f.exists():
            return HTMLResponse(content=f.read_text(encoding="utf-8"), status_code=200)
        return HTMLResponse(content="404 Not Found", status_code=404)

    @app.get("/health")
    @app.get("/api/health")
    @app.get("/healthz")
    async def universal_health_check():
        edition = os.environ.get(
            "KARGOPILOT_EDITION",
            "managed_cloud" if os.environ.get("PCS_MANAGED_CLOUD") == "1" else "sovereign",
        )
        return {
            "status": "healthy",
            "version": "6.5.0",
            "edition": edition,
            "service": "kargopilot-core",
            "dual_hosting_ready": True,
            "capabilities": [
                "multi_tenant",
                "customs_supervisor",
                "smart_arbitrage",
                "data_sovereignty",
                "export_ready",
            ],
            "timestamp": int(time.time()),
            "bind": f"{HOST}:{PORT}",
        }

    @app.get("/api/export/data")
    async def export_user_data():
        """Exports user data in compliant JSON format as required by Dual-Hosting Master Prompt."""
        from app.database import (
            get_all_orders,
            get_all_declarations,
            get_fin_profiles,
            get_db_metrics,
        )
        try:
            orders = get_all_orders(limit=500)
            declarations = get_all_declarations()
            profiles = get_fin_profiles()
            metrics = get_db_metrics()
        except Exception as exc:
            orders, declarations, profiles, metrics = [], [], [], {"error": str(exc)}

        return JSONResponse(
            content={
                "project": "KargoPilot v6.5 Enterprise",
                "export_version": "1.0",
                "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "edition": os.environ.get("KARGOPILOT_EDITION", "sovereign"),
                "metrics": metrics,
                "data": {
                    "orders": orders,
                    "customs_declarations": declarations,
                    "fin_profiles": profiles,
                },
                "compliance": {
                    "law": "Azərbaycan Respublikasının 'Fərdi məlumatlar haqqında' Qanunu",
                    "sovereignty_guarantee": "Zero telemetry to third parties in Sovereign Edition.",
                },
            },
            headers={
                "Content-Disposition": f'attachment; filename="kargopilot_export_{int(time.time())}.json"'
            },
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        f = BASE_DIR / "app" / "templates" / "404.html"
        if f.exists():
            return HTMLResponse(status_code=404, content=f.read_text(encoding="utf-8"))
        return HTMLResponse(
            status_code=404,
            content="""
            <div style="font-family:'Schibsted Grotesk',sans-serif; text-align:center; padding:60px; background:#0b0f14; color:#f4f7fa; min-height:100svh;">
                <h1 style="color:#dafa9c; font-size:48px; margin-bottom:10px;">404</h1>
                <h2>Səhifə Tapılmadı</h2>
                <p style="color:#9badc4;">Axtardığınız səhifə mövcud deyil və ya ünvan dəyişdirilib.</p>
                <a href="/" style="display:inline-block; margin-top:20px; padding:12px 24px; background:#dafa9c; color:#0b0f14; text-decoration:none; border-radius:10px; font-weight:800;">İdarəetmə Mərkəzinə Qayıt</a>
            </div>
            """,
        )

    return app


app = create_app()
