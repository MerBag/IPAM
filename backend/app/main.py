import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings
from app.routers import allocations, audit, auth, dashboard, health, inventory, ip_addresses, prefixes, search, subnets, users


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
)

origins = settings.cors_origins_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials="*" not in origins,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts_list)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:128]
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


for api_router in (
    health.router,
    auth.router,
    users.router,
    dashboard.router,
    prefixes.router,
    subnets.router,
    ip_addresses.router,
    allocations.router,
    inventory.router,
    search.router,
    audit.router,
):
    app.include_router(api_router, prefix=settings.api_prefix)


@app.get(settings.api_prefix, include_in_schema=False)
def api_root():
    return {"name": settings.app_name, "version": app.version, "docs": f"{settings.api_prefix}/docs"}
