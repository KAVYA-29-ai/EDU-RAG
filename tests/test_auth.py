import os, sys, pathlib, pytest
from unittest.mock import MagicMock, patch
from starlette.middleware.base import BaseHTTPMiddleware

# ── Setup ─────────────────────────────────────────────────────────────────────
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))

_mock_sb = MagicMock()

def _fake_db():
    return _mock_sb

class _Noop(BaseHTTPMiddleware):
    async def dispatch(self, req, call_next):
        return await call_next(req)

patch("database.init_supabase", lambda: None).start()
patch("database.get_supabase", _fake_db).start()
patch("database.supabase_admin", _mock_sb).start()
patch("database.supabase", _mock_sb).start()
patch("main.RateLimitMiddleware", _Noop).start()

from main import app  # noqa — after patches

# Patch get_supabase in routers directly (they import it at load time)
import routers.auth as _r_auth
_r_auth.get_supabase = _fake_db

from fastapi.testclient import TestClient
_client = TestClient(app, raise_server_exceptions=False)

# ── Helpers ───────────────────────────────────────────────────────────────────
from passlib.context import CryptContext
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _hash(p): return _pwd.hash(p)

def _user(role="student", pw="testpass123"):
    return {"id": f"uuid-{role}", "name": f"{role} user",
            "institution_id": f"{role}001", "email": f"{role}@t.com",
            "role": role, "avatar": "male", "status": "active",
            "password_hash": _hash(pw)}

def _set_user(u):
    _mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[u])

def _jwt(role="student"):
    from jose import jwt as j
    from datetime import datetime, timedelta
    return j.encode({"user_id": f"uuid-{role}", "institution_id": f"{role}001",
                     "role": role, "exp": datetime.utcnow() + timedelta(minutes=60)},
                    os.getenv("JWT_SECRET", "your-secret-key"), algorithm="HS256")

def _tok(role="student"):
    _set_user(_user(role))
    r = _client.post("/api/auth/login", json={"institution_id": f"{role}001", "password": "testpass123"})
    if r.status_code != 200: return None
    return r.json().get("access_token") or r.json().get("token")

@pytest.fixture(autouse=True)
def _reset():
    _mock_sb.reset_mock()
    _mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    _mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
    yield

# ── Tests ─────────────────────────────────────────────────────────────────────

class TestRegister:
    def test_success(self):
        _mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        _mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[_user()])
        r = _client.post("/api/auth/register", json={"name": "T", "institution_id": "student001",
            "email": "t@t.com", "password": "testpass123", "role": "student", "avatar": "male"})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_duplicate_400(self):
        _mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[_user()])
        r = _client.post("/api/auth/register", json={"name": "T", "institution_id": "student001",
            "email": "x@x.com", "password": "testpass123", "role": "student", "avatar": "male"})
        assert r.status_code == 400

    def test_missing_name_422(self):
        r = _client.post("/api/auth/register", json={"institution_id": "x", "password": "p", "role": "student", "avatar": "male"})
        assert r.status_code == 422

    def test_missing_password_422(self):
        r = _client.post("/api/auth/register", json={"name": "T", "institution_id": "x", "role": "student", "avatar": "male"})
        assert r.status_code == 422

    def test_invalid_role_rejected(self):
        r = _client.post("/api/auth/register", json={"name": "T", "institution_id": "x",
            "email": "t@t.com", "password": "p", "role": "superadmin", "avatar": "male"})
        assert r.status_code in [400, 422]

class TestLogin:
    def test_success(self):
        _set_user(_user())
        r = _client.post("/api/auth/login", json={"institution_id": "student001", "password": "testpass123"})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_token_has_role(self):
        from jose import jwt as j
        _set_user(_user("teacher"))
        r = _client.post("/api/auth/login", json={"institution_id": "teacher001", "password": "testpass123"})
        assert r.status_code == 200
        p = j.decode(r.json()["access_token"], os.getenv("JWT_SECRET", "your-secret-key"), algorithms=["HS256"])
        assert p["role"] == "teacher"

    def test_wrong_password_401(self):
        _set_user(_user("student", pw="correct"))
        r = _client.post("/api/auth/login", json={"institution_id": "student001", "password": "WRONG"})
        assert r.status_code == 401

    def test_nonexistent_401(self):
        _mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        r = _client.post("/api/auth/login", json={"institution_id": "nobody", "password": "any"})
        assert r.status_code == 401

    def test_missing_institution_id_422(self):
        r = _client.post("/api/auth/login", json={"password": "p"})
        assert r.status_code == 422

    def test_missing_password_422(self):
        r = _client.post("/api/auth/login", json={"institution_id": "x"})
        assert r.status_code == 422

    def test_response_has_user(self):
        _set_user(_user("admin"))
        r = _client.post("/api/auth/login", json={"institution_id": "admin001", "password": "testpass123"})
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "admin"

class TestMe:
    def test_valid_token_200(self):
        u = _user("teacher")
        _set_user(u)
        tok = _tok("teacher")
        assert tok, "Login returned no token"
        _set_user(u)
        r = _client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200

    def test_no_token_auth_error(self):
        r = _client.get("/api/auth/me")
        assert r.status_code in [401, 403]

    def test_fake_token_401(self):
        r = _client.get("/api/auth/me", headers={"Authorization": "Bearer fake.token.here"})
        assert r.status_code == 401

    def test_expired_token_401(self):
        from jose import jwt as j
        from datetime import datetime, timedelta
        tok = j.encode({"user_id": "x", "role": "student", "exp": datetime.utcnow() - timedelta(hours=1)},
                       os.getenv("JWT_SECRET", "your-secret-key"), algorithm="HS256")
        r = _client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401
