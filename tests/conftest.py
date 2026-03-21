import os
from unittest.mock import MagicMock, patch
from starlette.middleware.base import BaseHTTPMiddleware

# ── Step 1: Env vars first ────────────────────────────────────────────────────
os.environ["JWT_SECRET"] = "your-secret-key"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"
os.environ["SUPABASE_URL"] = "https://mock.supabase.co"
os.environ["SUPABASE_KEY"] = "mock-anon-key"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "mock-service-key"
os.environ["GEMINI_API_KEY"] = "mock-gemini-key"

# ── Step 2: Shared mock Supabase client ───────────────────────────────────────
mock_sb = MagicMock()

def fake_get_supabase():
    return mock_sb

# ── Step 3: Noop middleware to kill rate limiting ─────────────────────────────
class _NoopMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        return await call_next(request)

# ── Step 4: Patch EVERYTHING before app is imported ──────────────────────────
# These patches stay active for the entire test session
_patches = [
    patch("database.init_supabase", lambda: None),
    patch("database.get_supabase", fake_get_supabase),
    patch("database.supabase_admin", mock_sb),
    patch("database.supabase", mock_sb),
]

for p in _patches:
    p.start()

# Patch RateLimitMiddleware before main.py is imported
import sys
import types

# Create a fake main module stub so when test files do `from main import app`
# they get our patched version
_main_patch = patch("main.RateLimitMiddleware", _NoopMiddleware)
_main_patch.start()

# ── Step 5: Now import and expose app + mock_sb ───────────────────────────────
from main import app  # noqa: E402  — must be after patches
from fastapi.testclient import TestClient

# Expose for test files to import
__all__ = ["app", "mock_sb", "fake_get_supabase", "TestClient"]