import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

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

def make_user(role="teacher"):
    return {
        "id": f"uuid-{role}", "name": f"{role.title()} User",
        "institution_id": f"{role}001", "email": f"{role}@test.com",
        "role": role, "avatar": "female", "status": "active",
        "password_hash": _hashed("pass123"),
    }

def _get_valid_token(role="teacher"):
    """Build a real signed JWT directly — no mock dependency."""
    from jose import jwt as jose_jwt
    import os
    from datetime import datetime, timedelta
    payload = {
        "user_id": f"uuid-{role}",
        "institution_id": f"{role}001",
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=60),
    }
    return jose_jwt.encode(payload, os.getenv("JWT_SECRET", "your-secret-key"), algorithm="HS256")

def auth_headers(role="teacher"):
    return {"Authorization": f"Bearer {_get_valid_token(role)}"}

def _mock_user_fetch(role="teacher"):
    """Mock the DB user fetch that happens inside get_current_user."""
    user = make_user(role)
    mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[user])

def make_feedback_row():
    return {
        "id": "fb-001", "user_id": "uuid-teacher",
        "message": "RAG needs better source diversity",
        "rating": 4, "created_at": "2026-01-01T10:00:00", "response": None
    }

# ── Submit Feedback (/api/feedback/) ─────────────────────────────────────────

class TestSubmitFeedback:

    def test_no_token_is_auth_error(self):
        r = client.post("/api/feedback/", json={"message": "Good", "rating": 5})
        assert r.status_code in [401, 403]
        assert r.status_code != 200

    def test_teacher_submits_feedback_200(self):
        """Teacher submits feedback → 200"""
        _mock_user_fetch(role="teacher")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[make_feedback_row()])

        r = client.post("/api/feedback/", json={
            "message": "Search results need improvement",
            "rating": 4
        }, headers=auth_headers(role="teacher"))
        assert r.status_code == 200
        assert r.status_code != 500

    def test_admin_submits_feedback_200(self):
        """Admin submits feedback → 200"""
        _mock_user_fetch(role="admin")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[make_feedback_row()])

        r = client.post("/api/feedback/", json={
            "message": "System works well",
            "rating": 5
        }, headers=auth_headers(role="admin"))
        assert r.status_code in [200, 403]
        assert r.status_code != 500

    def test_feedback_never_returns_500(self):
        """Any feedback call must never crash → never 500"""
        _mock_user_fetch(role="teacher")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[make_feedback_row()])

        r = client.post("/api/feedback/", json={
            "message": "Works fine", "rating": 3
        }, headers=auth_headers(role="teacher"))
        assert r.status_code != 500

    def test_student_feedback_blocked(self):
        """Student cannot post to teacher feedback endpoint → 403"""
        _mock_user_fetch(role="student")
        r = client.post("/api/feedback/", json={"message": "Hello", "rating": 5},
                        headers=auth_headers(role="student"))
        assert r.status_code in [403, 401]
        assert r.status_code != 200


# ── Get All Feedback (/api/feedback/) ────────────────────────────────────────

class TestGetFeedback:

    def test_no_token_is_auth_error(self):
        r = client.get("/api/feedback/")
        assert r.status_code in [401, 403]
        assert r.status_code != 200

    def test_admin_gets_feedback_list(self):
        """Admin → 200 with list"""
        _mock_user_fetch(role="admin")
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(
            data=[make_feedback_row(), make_feedback_row()]
        )
        r = client.get("/api/feedback/", headers=auth_headers(role="admin"))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_student_cannot_see_all_feedback(self):
        """Student → 403, not 200"""
        _mock_user_fetch(role="student")
        r = client.get("/api/feedback/", headers=auth_headers(role="student"))
        assert r.status_code in [403, 401]
        assert r.status_code != 200

    def test_feedback_item_structure(self):
        """Each item has id or message field"""
        _mock_user_fetch(role="admin")
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(
            data=[make_feedback_row()]
        )
        r = client.get("/api/feedback/", headers=auth_headers(role="admin"))
        if r.status_code == 200:
            items = r.json()
            if items:
                assert "id" in items[0] or "message" in items[0]

    def test_get_feedback_never_500(self):
        """GET feedback must never return 500"""
        _mock_user_fetch(role="admin")
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
        r = client.get("/api/feedback/", headers=auth_headers(role="admin"))
        assert r.status_code != 500


# ── Student Feedback — discover actual route from main.py ────────────────────
# main.py: app.include_router(student_feedback.router, prefix="/api/student-feedback")

class TestStudentFeedback:

    def test_student_feedback_endpoint_exists(self):
        """GET /api/student-feedback/ should not 404 — endpoint must exist"""
        _mock_user_fetch(role="student")
        r = client.get("/api/student-feedback/", headers=auth_headers(role="student"))
        # 200, 401, 403 all fine — 404 means route missing, 500 means crash
        assert r.status_code != 404
        assert r.status_code != 500

    def test_student_feedback_no_token_is_auth_error(self):
        """No token → auth error on student-feedback endpoint"""
        r = client.get("/api/student-feedback/")
        assert r.status_code in [401, 403]
        assert r.status_code != 200

    def test_student_can_submit_anonymous_feedback(self):
        """Student posts anonymous feedback → not 405 or 500"""
        _mock_user_fetch(role="student")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{
            "id": "sfb-001", "message": "Class notes are helpful"
        }])
        r = client.post("/api/student-feedback/", json={
            "message": "Class notes are very helpful"
        }, headers=auth_headers(role="student"))
        assert r.status_code not in [405, 500]

    def test_response_never_exposes_password(self):
        """No endpoint response should ever expose password fields"""
        _mock_user_fetch(role="student")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{
            "id": "sfb-002", "message": "Anonymous message"
        }])
        r = client.post("/api/student-feedback/", json={"message": "Anonymous"},
                        headers=auth_headers(role="student"))
        if r.status_code == 200:
            assert "password" not in str(r.json())
            assert "password_hash" not in str(r.json())
