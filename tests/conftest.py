import os
import sys
import pathlib
from unittest.mock import MagicMock, patch
from starlette.middleware.base import BaseHTTPMiddleware

# ── tests/ folder ko sys.path mein daalo ─────────────────────────────────────
sys.path.insert(0, str(pathlib.Path(__file__).parent))

# ── Env vars ──────────────────────────────────────────────────────────────────
os.environ["JWT_SECRET"] = "your-secret-key"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"
os.environ["SUPABASE_URL"] = "https://mock.supabase.co"
os.environ["SUPABASE_KEY"] = "mock-anon-key"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "mock-service-key"
os.environ["GEMINI_API_KEY"] = "mock-gemini-key"

# ── Global shared mock ────────────────────────────────────────────────────────
mock_sb = MagicMock()

def fake_get_supabase():
    return mock_sb

# ── Kill rate limiter ─────────────────────────────────────────────────────────
class _NoopMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        return await call_next(request)

# ── Patch BEFORE any app import ───────────────────────────────────────────────
patch("database.init_supabase", lambda: None).start()
patch("database.get_supabase", fake_get_supabase).start()
patch("database.supabase_admin", mock_sb).start()
patch("database.supabase", mock_sb).start()
patch("main.RateLimitMiddleware", _NoopMiddleware).start()

# ── Import app after patches ──────────────────────────────────────────────────
from main import app  # noqa
from fastapi.testclient import TestClient
client = TestClient(app, raise_server_exceptions=False)