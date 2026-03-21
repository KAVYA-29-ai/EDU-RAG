import pytest, os
from unittest.mock import MagicMock
from shared_fixtures import client, mock_sb, auth, make_user, mock_user, _hashed, _jwt


@pytest.fixture(autouse=True)
def reset():
    mock_sb.reset_mock()
    mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
    yield


def _login_mock(user):
    mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[user])


def _get_token(role="student"):
    user = make_user(role)
    _login_mock(user)
    r = client.post("/api/auth/login", json={
        "institution_id": f"{role}001",
        "password": "testpass123"
    })
    if r.status_code != 200:
        return None
    return r.json().get("access_token") or r.json().get("token")


# ── Register ──────────────────────────────────────────────────────────────────

class TestRegister:

    def test_success(self):
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[make_user()])
        r = client.post("/api/auth/register", json={
            "name": "Test", "institution_id": "student001",
            "email": "t@t.com", "password": "testpass123",
            "role": "student", "avatar": "male"
        })
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_duplicate_400(self):
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[make_user()])
        r = client.post("/api/auth/register", json={
            "name": "Another", "institution_id": "student001",
            "email": "x@x.com", "password": "testpass123",
            "role": "student", "avatar": "male"
        })
        assert r.status_code == 400

    def test_missing_name_422(self):
        r = client.post("/api/auth/register", json={
            "institution_id": "test123", "password": "testpass123",
            "role": "student", "avatar": "male"
        })
        assert r.status_code == 422

    def test_missing_password_422(self):
        r = client.post("/api/auth/register", json={
            "name": "Test", "institution_id": "test123",
            "role": "student", "avatar": "male"
        })
        assert r.status_code == 422

    def test_invalid_role_rejected(self):
        r = client.post("/api/auth/register", json={
            "name": "Test", "institution_id": "test123",
            "email": "t@t.com", "password": "testpass123",
            "role": "superadmin", "avatar": "male"
        })
        assert r.status_code in [400, 422]


# ── Login ─────────────────────────────────────────────────────────────────────

class TestLogin:

    def test_success(self):
        _login_mock(make_user("student"))
        r = client.post("/api/auth/login", json={
            "institution_id": "student001", "password": "testpass123"
        })
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_token_has_role(self):
        from jose import jwt as jose_jwt
        _login_mock(make_user("teacher"))
        r = client.post("/api/auth/login", json={
            "institution_id": "teacher001", "password": "testpass123"
        })
        assert r.status_code == 200
        payload = jose_jwt.decode(
            r.json()["access_token"],
            os.getenv("JWT_SECRET", "your-secret-key"),
            algorithms=["HS256"]
        )
        assert payload["role"] == "teacher"

    def test_wrong_password_401(self):
        _login_mock(make_user("student", password="correct"))
        r = client.post("/api/auth/login", json={
            "institution_id": "student001", "password": "WRONG"
        })
        assert r.status_code == 401

    def test_nonexistent_401(self):
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        r = client.post("/api/auth/login", json={
            "institution_id": "nobody", "password": "any"
        })
        assert r.status_code == 401

    def test_missing_institution_id_422(self):
        r = client.post("/api/auth/login", json={"password": "testpass123"})
        assert r.status_code == 422

    def test_missing_password_422(self):
        r = client.post("/api/auth/login", json={"institution_id": "student001"})
        assert r.status_code == 422

    def test_response_has_user(self):
        _login_mock(make_user("admin"))
        r = client.post("/api/auth/login", json={
            "institution_id": "admin001", "password": "testpass123"
        })
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "admin"


# ── /me ───────────────────────────────────────────────────────────────────────

class TestMe:

    def test_valid_token_200(self):
        user = make_user("teacher")
        _login_mock(user)
        token = _get_token("teacher")
        assert token, "Login failed — token is None"
        # Re-mock for the /me DB fetch
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[user])
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200

    def test_no_token_auth_error(self):
        r = client.get("/api/auth/me")
        assert r.status_code in [401, 403]

    def test_fake_token_401(self):
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer fake.token.here"})
        assert r.status_code == 401

    def test_expired_token_401(self):
        from jose import jwt as jose_jwt
        from datetime import datetime, timedelta
        expired = jose_jwt.encode(
            {"user_id": "uuid-student", "role": "student",
             "exp": datetime.utcnow() - timedelta(hours=1)},
            os.getenv("JWT_SECRET", "your-secret-key"), algorithm="HS256"
        )
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
        assert r.status_code == 401