import os
from unittest.mock import patch, MagicMock

# ── Env vars BEFORE any import ───────────────────────────────────────────────
os.environ.setdefault("JWT_SECRET", "your-secret-key")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("SUPABASE_URL", "https://mock.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "mock-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "mock-service-key")
os.environ.setdefault("GEMINI_API_KEY", "mock-gemini-key")

# ── Disable RateLimitMiddleware so tests never hit 429 ───────────────────────
# main.py adds RateLimitMiddleware — we patch it to a passthrough before import
from starlette.middleware.base import BaseHTTPMiddleware

class _NoopMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        return await call_next(request)

patch("main.RateLimitMiddleware", _NoopMiddleware).start()
