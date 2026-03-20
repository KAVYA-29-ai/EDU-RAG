import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# ── Patch BEFORE app import ──────────────────────────────────────────────────
mock_sb = MagicMock()

def fake_get_supabase():
    return mock_sb

with patch("database.init_supabase", lambda: None), \
     patch("database.get_supabase", fake_get_supabase):
    from main import app

client = TestClient(app, raise_server_exceptions=False)

# ── Helpers ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_mock():
    mock_sb.reset_mock()
    mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
    yield

def _hashed(plain: str) -> str:
    from passlib.context import CryptContext
    return CryptContext(schemes=["bcrypt"], deprecated="auto").hash(plain)

def make_user(role="student", password="testpass123"):
    return {
        "id": "uuid-001",
        "name": "Test User",
        "institution_id": "test123",
        "email": "test@example.com",
        "role": role,
        "avatar": "male",
        "status": "active",
        "password_hash": _hashed(password),
    }

def setup_login_mock(user: dict):
    mock_sb.table.return_value \
           .select.return_value \
           .eq.return_value \
           .limit.return_value \
           .execute.return_value = MagicMock(data=[user])

def get_token(role="student", password="testpass123"):
    user = make_user(role=role, password=password)
    setup_login_mock(user)
    r = client.post("/api/auth/login", json={
        "institution_id": "test123",
        "password": password
    })
    if r.status_code != 200:
        return None
    d = r.json()
    return d.get("access_token") or d.get("token")

def auth_headers(role="student"):
    tok = get_token(role)
    return {"Authorization": f"Bearer {tok}"} if tok else {}

# ── Register ─────────────────────────────────────────────────────────────────

class TestRegister:

    def test_register_success(self):
        """New user → 200 with access_token"""
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[make_user()])

        r = client.post("/api/auth/register", json={
            "name": "Test User",
            "institution_id": "test123",
            "email": "test@example.com",
            "password": "testpass123",
            "role": "student",
            "avatar": "male"
        })
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_register_duplicate_returns_400(self):
        """Existing institution_id → 400, not 500"""
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[make_user()])

        r = client.post("/api/auth/register", json={
            "name": "Another",
            "institution_id": "test123",
            "email": "x@x.com",
            "password": "testpass123",
            "role": "student",
            "avatar": "male"
        })
        assert r.status_code == 400
        assert r.status_code != 500

    def test_register_missing_name_422(self):
        r = client.post("/api/auth/register", json={
            "institution_id": "test123",
            "password": "testpass123",
            "role": "student",
            "avatar": "male"
        })
        assert r.status_code == 422

    def test_register_missing_password_422(self):
        r = client.post("/api/auth/register", json={
            "name": "Test",
            "institution_id": "test123",
            "role": "student",
            "avatar": "male"
        })
        assert r.status_code == 422

    def test_register_invalid_role_rejected(self):
        r = client.post("/api/auth/register", json={
            "name": "Test",
            "institution_id": "test123",
            "email": "t@t.com",
            "password": "testpass123",
            "role": "superadmin",
            "avatar": "male"
        })
        assert r.status_code in [400, 422]


# ── Login ─────────────────────────────────────────────────────────────────────

class TestLogin:

    def test_login_success_returns_token(self):
        """Valid credentials → 200 + access_token"""
        setup_login_mock(make_user())
        r = client.post("/api/auth/login", json={
            "institution_id": "test123",
            "password": "testpass123"
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["access_token"] != ""

    def test_login_token_is_valid_jwt_with_role(self):
        """Returned token must be decodable JWT with role claim"""
        from jose import jwt as jose_jwt
        import os
        setup_login_mock(make_user(role="teacher"))
        r = client.post("/api/auth/login", json={
            "institution_id": "test123",
            "password": "testpass123"
        })
        assert r.status_code == 200
        token = r.json()["access_token"]
        secret = os.getenv("JWT_SECRET", "your-secret-key")
        payload = jose_jwt.decode(token, secret, algorithms=["HS256"])
        assert "role" in payload
        assert payload["role"] == "teacher"

    def test_login_wrong_password_401(self):
        """Wrong password → 401, not 200"""
        setup_login_mock(make_user(password="correctpass"))
        r = client.post("/api/auth/login", json={
            "institution_id": "test123",
            "password": "WRONGPASSWORD"
        })
        assert r.status_code == 401
        assert r.status_code != 200

    def test_login_nonexistent_user_401(self):
        """User not in DB → 401"""
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        r = client.post("/api/auth/login", json={
            "institution_id": "ghost_user",
            "password": "anypassword"
        })
        assert r.status_code == 401
        assert r.status_code != 200

    def test_login_missing_institution_id_422(self):
        r = client.post("/api/auth/login", json={"password": "testpass123"})
        assert r.status_code == 422

    def test_login_missing_password_422(self):
        r = client.post("/api/auth/login", json={"institution_id": "test123"})
        assert r.status_code == 422

    def test_login_response_has_user_object(self):
        """Response contains user object with role"""
        setup_login_mock(make_user(role="admin"))
        r = client.post("/api/auth/login", json={
            "institution_id": "test123",
            "password": "testpass123"
        })
        assert r.status_code == 200
        data = r.json()
        assert "user" in data
        assert data["user"]["role"] == "admin"


# ── /me ───────────────────────────────────────────────────────────────────────

class TestMe:

    def test_me_valid_token_200(self):
        """Valid JWT → 200 with user info"""
        user = make_user(role="teacher")
        setup_login_mock(user)
        token = get_token(role="teacher")
        assert token, "Could not get token from login"

        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[user])
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        assert "role" in data or "institution_id" in data

    def test_me_no_token_is_auth_error(self):
        """No token → auth failure (FastAPI HTTPBearer gives 403, both 401/403 are valid auth errors)"""
        r = client.get("/api/auth/me")
        assert r.status_code in [401, 403]
        assert r.status_code != 200
        assert r.status_code != 500

    def test_me_invalid_token_401(self):
        """Tampered token → 401"""
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer totally.fake.token"})
        assert r.status_code == 401
        assert r.status_code != 200

    def test_me_expired_token_401(self):
        """Expired token → 401"""
        from jose import jwt as jose_jwt
        from datetime import datetime, timedelta
        import os
        expired = jose_jwt.encode(
            {"user_id": "uuid-001", "role": "student",
             "exp": datetime.utcnow() - timedelta(hours=1)},
            os.getenv("JWT_SECRET", "your-secret-key"),
            algorithm="HS256"
        )
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
        assert r.status_code == 401
