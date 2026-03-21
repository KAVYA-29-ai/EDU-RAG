# shared_fixtures.py
# Set up environment variables and patch dependencies before importing main.
import os
from unittest.mock import MagicMock, patch
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.testclient import TestClient

os.environ["JWT_SECRET"] = "your-secret-key"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"
os.environ["SUPABASE_URL"] = "https://mock.supabase.co"
os.environ["SUPABASE_KEY"] = "mock-anon-key"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "mock-service-key"
os.environ["GEMINI_API_KEY"] = "mock-gemini-key"

mock_sb = MagicMock()

def fake_get_supabase():
    return mock_sb

class _NoopMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        return await call_next(request)

# Apply all patches
patch("database.init_supabase", lambda: None).start()
patch("database.get_supabase", fake_get_supabase).start()
patch("database.supabase_admin", mock_sb).start()
patch("database.supabase", mock_sb).start()
patch("main.RateLimitMiddleware", _NoopMiddleware).start()

# Now it is safe to import app because dependencies are mocked
from main import app  # noqa
client = TestClient(app, raise_server_exceptions=False)


def _hashed(plain):
    from passlib.context import CryptContext
    return CryptContext(schemes=["bcrypt"], deprecated="auto").hash(plain)


def _jwt(role="student", institution_id=None):
    from jose import jwt as jose_jwt
    from datetime import datetime, timedelta
    return jose_jwt.encode(
        {
            "user_id": f"uuid-{role}",
            "institution_id": institution_id or f"{role}001",
            "role": role,
            "exp": datetime.utcnow() + timedelta(minutes=60),
        },
        os.getenv("JWT_SECRET", "your-secret-key"),
        algorithm="HS256",
    )


def auth(role="student"):
    return {"Authorization": f"Bearer {_jwt(role)}"}


def make_user(role="student", institution_id=None, password="testpass123"):
    return {
        "id": f"uuid-{role}",
        "name": f"{role.title()} User",
        "institution_id": institution_id or f"{role}001",
        "email": f"{role}@test.com",
        "role": role,
        "avatar": "male",
        "status": "active",
        "password_hash": _hashed(password),
    }


def mock_user(role="student"):
    mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[make_user(role)]
    )