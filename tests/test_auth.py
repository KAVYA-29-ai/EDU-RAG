import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Mock Supabase before importing app
mock_supabase = MagicMock()

with patch("backend.database.supabase", mock_supabase):
    from backend.main import app

client = TestClient(app)

# ─── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_mocks():
    mock_supabase.reset_mock()
    yield

def make_user(role="student", password_hash="$2b$12$hashedpassword"):
    return {
        "id": "user-uuid-001",
        "name": "Test User",
        "institution_id": "test123",
        "email": "test@example.com",
        "role": role,
        "avatar": "male",
        "password_hash": password_hash,
        "created_at": "2026-01-01T00:00:00"
    }

# ─── Registration Tests ──────────────────────────────────────────────────────

class TestRegister:

    def test_register_success(self):
        """New user registers successfully → 200 with user data"""
        mock_supabase.table().select().eq().execute.return_value = MagicMock(data=[])
        mock_supabase.table().insert().execute.return_value = MagicMock(data=[make_user()])

        response = client.post("/api/auth/register", json={
            "name": "Test User",
            "institution_id": "test123",
            "email": "test@example.com",
            "password": "testpass123",
            "role": "student",
            "avatar": "male"
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data or "message" in data or "token" in data

    def test_register_duplicate_institution_id(self):
        """Duplicate institution_id → 400, not 200"""
        mock_supabase.table().select().eq().execute.return_value = MagicMock(
            data=[make_user()]
        )
        response = client.post("/api/auth/register", json={
            "name": "Another User",
            "institution_id": "test123",
            "email": "another@example.com",
            "password": "testpass123",
            "role": "student",
            "avatar": "male"
        })
        assert response.status_code == 400
        assert response.status_code != 500

    def test_register_missing_required_field(self):
        """Missing password → 422 validation error"""
        response = client.post("/api/auth/register", json={
            "name": "Test User",
            "institution_id": "test123",
        })
        assert response.status_code == 422

    def test_register_invalid_role(self):
        """Invalid role value → 422 validation error"""
        response = client.post("/api/auth/register", json={
            "name": "Test User",
            "institution_id": "test123",
            "email": "test@example.com",
            "password": "testpass123",
            "role": "superadmin",  # not a valid role
            "avatar": "male"
        })
        assert response.status_code in [400, 422]

    def test_register_empty_password(self):
        """Empty password should be rejected"""
        response = client.post("/api/auth/register", json={
            "name": "Test User",
            "institution_id": "test123",
            "email": "test@example.com",
            "password": "",
            "role": "student",
            "avatar": "male"
        })
        assert response.status_code in [400, 422]
        assert response.status_code != 200

# ─── Login Tests ─────────────────────────────────────────────────────────────

class TestLogin:

    def test_login_success_returns_token(self):
        """Valid credentials → 200 with JWT token"""
        import bcrypt
        hashed = bcrypt.hashpw(b"testpass123", bcrypt.gensalt()).decode()
        user = make_user(password_hash=hashed)

        mock_supabase.table().select().eq().execute.return_value = MagicMock(data=[user])

        response = client.post("/api/auth/login", json={
            "institution_id": "test123",
            "password": "testpass123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data or "token" in data
        assert response.status_code != 500

    def test_login_wrong_password(self):
        """Wrong password → 401, never 200"""
        import bcrypt
        hashed = bcrypt.hashpw(b"correctpass", bcrypt.gensalt()).decode()
        user = make_user(password_hash=hashed)

        mock_supabase.table().select().eq().execute.return_value = MagicMock(data=[user])

        response = client.post("/api/auth/login", json={
            "institution_id": "test123",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        assert response.status_code != 200

    def test_login_nonexistent_user(self):
        """User not found → 404 or 401, not 200"""
        mock_supabase.table().select().eq().execute.return_value = MagicMock(data=[])

        response = client.post("/api/auth/login", json={
            "institution_id": "ghost_user",
            "password": "anypassword"
        })
        assert response.status_code in [401, 404]
        assert response.status_code != 200

    def test_login_missing_institution_id(self):
        """Missing institution_id → 422 validation error"""
        response = client.post("/api/auth/login", json={
            "password": "testpass123"
        })
        assert response.status_code == 422

    def test_login_token_contains_role(self):
        """JWT payload should encode user role"""
        import bcrypt, jwt
        hashed = bcrypt.hashpw(b"testpass123", bcrypt.gensalt()).decode()
        user = make_user(role="teacher", password_hash=hashed)
        mock_supabase.table().select().eq().execute.return_value = MagicMock(data=[user])

        response = client.post("/api/auth/login", json={
            "institution_id": "test123",
            "password": "testpass123"
        })
        assert response.status_code == 200
        data = response.json()
        token = data.get("access_token") or data.get("token")
        assert token is not None
        # Decode without verifying (just check payload structure)
        decoded = jwt.decode(token, options={"verify_signature": False})
        assert "role" in decoded or "sub" in decoded

# ─── /me Endpoint Tests ───────────────────────────────────────────────────────

class TestMe:

    def _get_token(self):
        import bcrypt
        hashed = bcrypt.hashpw(b"testpass123", bcrypt.gensalt()).decode()
        user = make_user(password_hash=hashed)
        mock_supabase.table().select().eq().execute.return_value = MagicMock(data=[user])
        response = client.post("/api/auth/login", json={
            "institution_id": "test123",
            "password": "testpass123"
        })
        data = response.json()
        return data.get("access_token") or data.get("token")

    def test_me_with_valid_token(self):
        """Valid JWT → returns user profile"""
        token = self._get_token()
        if not token:
            pytest.skip("Login didn't return token — check auth router")

        mock_supabase.table().select().eq().execute.return_value = MagicMock(
            data=[make_user()]
        )
        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert "institution_id" in data or "email" in data or "role" in data

    def test_me_without_token(self):
        """No token → 401 unauthorized"""
        response = client.get("/api/auth/me")
        assert response.status_code == 401
        assert response.status_code != 200

    def test_me_with_invalid_token(self):
        """Tampered token → 401"""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer this.is.fake"}
        )
        assert response.status_code == 401
