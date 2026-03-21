"""
Shared mock setup — imported at the TOP of every test file BEFORE any other import.
This ensures database.supabase_admin is set before init_supabase() runs.
"""
import os, sys, pathlib
from unittest.mock import MagicMock
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict, deque

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))

# Env vars
os.environ.setdefault("JWT_SECRET", "your-secret-key")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("SUPABASE_URL", "https://mock.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "mock-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "mock-service-key")
os.environ.setdefault("GEMINI_API_KEY", "mock-gemini-key")

# Create mock BEFORE importing database
mock_sb = MagicMock()

def fake_get_supabase():
    return mock_sb

# Import database and IMMEDIATELY override supabase_admin
# This runs before init_supabase() can set it to None
import database
database.supabase_admin = mock_sb
database.supabase = mock_sb
database.init_supabase = lambda: None
database.get_supabase = fake_get_supabase

# Noop rate limiter
class NoopRateLimit(BaseHTTPMiddleware):
    async def dispatch(self, req, call_next):
        return await call_next(req)

# Import main AFTER database is patched
import main as _main
_main.RateLimitMiddleware = NoopRateLimit
_main._ip_buckets = defaultdict(lambda: deque())

# Patch get_supabase in every router that imported it
import routers.auth as _ra
import routers.feedback as _rf
import routers.student_feedback as _rsf
import routers.rag as _rrag

_ra.get_supabase = fake_get_supabase
_rf.get_supabase = fake_get_supabase
_rsf.get_supabase = fake_get_supabase
_rrag.get_supabase = fake_get_supabase

from fastapi.testclient import TestClient
client = TestClient(_main.app, raise_server_exceptions=False)