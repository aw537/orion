import hmac
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.storage.redis_client import get_redis, close_redis
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("orion")

# Paths exempt from the static bearer-token check (ORION_LOCAL_TOKEN).
# login/register/logout/me must be reachable without the server-level token.
_TOKEN_AUTH_EXEMPT_PATHS = {
    "/health", "/docs", "/openapi.json", "/redoc",
    "/api/v1/auth/register", "/api/v1/auth/login",
    "/api/v1/auth/logout", "/api/v1/auth/me",
}

# Paths exempt from rate limiting (static assets / health only).
# Login and register are intentionally NOT here so brute-force is limited.
_RATE_LIMIT_EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class TokenAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow CORS preflight through before any auth check
        if request.method == "OPTIONS":
            return await call_next(request)
        token = get_settings().ORION_LOCAL_TOKEN
        if token and request.url.path not in _TOKEN_AUTH_EXEMPT_PATHS:
            auth = request.headers.get("authorization", "")
            expected = f"Bearer {token}"
            if not hmac.compare_digest(auth, expected):
                return JSONResponse(status_code=401, content={"error": "Invalid or missing bearer token"})
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple sliding-window rate limiter. 120 requests per minute per client IP."""
    WINDOW = 60
    MAX_REQUESTS = 120
    EVICTION_INTERVAL = 300  # evict stale entries every 5 minutes

    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, list[float]] = {}
        self._last_eviction = time.monotonic()

    async def dispatch(self, request: Request, call_next):
        if get_settings().ORION_AUTH_DISABLED:
            return await call_next(request)
        if request.url.path in _RATE_LIMIT_EXEMPT_PATHS:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        cutoff = now - self.WINDOW
        # Periodic eviction of clients with no recent hits (prevents unbounded growth)
        if now - self._last_eviction > self.EVICTION_INTERVAL:
            self._hits = {ip: ts for ip, ts in self._hits.items() if any(t > cutoff for t in ts)}
            self._last_eviction = now
        window = [t for t in self._hits.get(client, []) if t > cutoff]
        if len(window) >= self.MAX_REQUESTS:
            return JSONResponse(status_code=429, content={"error": "Rate limit exceeded"}, headers={"Retry-After": str(self.WINDOW)})
        window.append(now)
        self._hits[client] = window
        return await call_next(request)


import asyncio as _asyncio


async def _session_prune_loop():
    """Background task: prune expired UserSession rows once per hour."""
    from app.database import async_session as _async_session
    from app.auth.service import prune_expired_sessions
    while True:
        await _asyncio.sleep(3600)
        try:
            async with _async_session() as db:
                n = await prune_expired_sessions(db)
                if n:
                    logger.info(f"Pruned {n} expired session(s)")
        except Exception as e:
            logger.warning(f"Session prune failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Orion API starting up")
    await get_redis()
    from app.scheduler.audit_scheduler import start_scheduler, stop_scheduler
    start_scheduler()
    prune_task = _asyncio.create_task(_session_prune_loop())
    yield
    prune_task.cancel()
    stop_scheduler()
    logger.info("Orion API shutting down — draining background tasks")
    from app.mcp.background import drain
    await drain(timeout=10.0)
    from app.storage.embedding_router import close_embedding_provider
    await close_embedding_provider()
    await close_redis()


app = FastAPI(title="Orion", version="0.1.0", description="AI-powered local knowledge architecture", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TokenAuthMiddleware)
app.add_middleware(RateLimitMiddleware)


from app.api import galaxy, planets, biomes, stardust, nebula, onboarding, search
from app.api import entities as entities_api
from app.api import cache as cache_api
from app.api import model_profiles as model_profiles_api
from app.api import sun as sun_api
from app.api import agents as agents_api
from app.api import graph as graph_api
from app.api import contradictions as contradictions_api
from app.api import synthesis as synthesis_api
from app.api import ask as ask_api
from app.api import admin as admin_api
from app.api import brain as brain_api
from app.api import routing as routing_api
from app.api import inbox as inbox_api
from app.auth.router import router as auth_router

app.include_router(auth_router)
app.include_router(galaxy.router)
app.include_router(planets.router)
app.include_router(biomes.router)
app.include_router(stardust.router)
app.include_router(nebula.router)
app.include_router(entities_api.router)
app.include_router(onboarding.router)
app.include_router(search.router)
app.include_router(cache_api.router)
app.include_router(model_profiles_api.router)
app.include_router(sun_api.router)
app.include_router(agents_api.router)
app.include_router(graph_api.router)
app.include_router(contradictions_api.router)
app.include_router(synthesis_api.router)
app.include_router(ask_api.router)
app.include_router(admin_api.router)
app.include_router(brain_api.router)
app.include_router(routing_api.router)
app.include_router(inbox_api.router)

# MCP server is now a separate service — see /mcp directory
# REST API serves all Orion functionality at /api/v1


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"error": str(exc)})

@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.get("/health")
async def health():
    status = {"status": "ok", "service": "orion-api", "version": "0.1.0", "degraded": []}
    # Check Redis
    try:
        redis = await get_redis()
        await redis.ping()
    except Exception:
        status["degraded"].append("redis")
    # Check Chroma
    try:
        from app.storage.chroma_client import get_chroma_client
        get_chroma_client().heartbeat()
    except Exception:
        status["degraded"].append("chroma")
    # Check Ollama
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{get_settings().OLLAMA_URL}/api/tags")
            if r.status_code != 200:
                status["degraded"].append("ollama")
    except Exception:
        status["degraded"].append("ollama")
    if status["degraded"]:
        status["status"] = "degraded"
    return status


@app.get("/api/v1/audit/status")
async def audit_status():
    from sqlalchemy import select, desc
    from app.database import async_session as asession
    from app.models.subagent import AuditRun
    async with asession() as db:
        run = (await db.execute(select(AuditRun).order_by(desc(AuditRun.run_at)).limit(1))).scalar_one_or_none()
        if not run:
            return {"status": "no_audits_run"}
        return {"id": run.id, "galaxy_id": run.galaxy_id, "run_at": run.run_at.isoformat(), "run_by": run.run_by, "records_reviewed": run.records_reviewed, "duplicates_merged": run.duplicates_merged, "contradictions_found": run.contradictions_found, "promotions_made": run.promotions_made, "confidence_decays": run.confidence_decays, "duration_ms": run.duration_ms, "summary": run.summary}


@app.post("/api/v1/audit/run")
async def trigger_audit():
    from sqlalchemy import select
    from app.database import async_session as asession
    from app.models import Galaxy
    from app.services import audit_service
    async with asession() as db:
        galaxy = (await db.execute(select(Galaxy).limit(1))).scalar_one_or_none()
        if not galaxy:
            return {"error": "No galaxy found"}
    result = await audit_service.run_audit(galaxy.id)
    return result
