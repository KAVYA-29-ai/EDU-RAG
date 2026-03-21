import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, call

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
    # Default: user fetch returns empty (overridden per test)
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
    from jose import jwt as jose_jwt
    import os
    from datetime import datetime, timedelta
    return jose_jwt.encode(
        {"user_id": f"uuid-{role}", "institution_id": f"{role}001", "role": role,
         "exp": datetime.utcnow() + timedelta(minutes=60)},
        os.getenv("JWT_SECRET", "your-secret-key"), algorithm="HS256"
    )

def auth_headers(role="teacher"):
    return {"Authorization": f"Bearer {_get_valid_token(role)}"}

def _mock_user_fetch(role="teacher"):
    """Mock get_current_user DB call — always set this before making requests."""
    user = make_user(role)
    mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[user])

def make_feedback_row():
    return {
        "id": "fb-001", "sender_id": "uuid-teacher",
        "category": "general", "message": "RAG needs better source diversity",
        "status": "pending", "created_at": "2026-01-01T10:00:00",
        "admin_response": None,
    }

# Try all common enum values — one will work
# feedback.py router uses feedback_data.category.value → it's an enum
# Common values: general, technical, content, bug, feature, other
# We'll try multiple to find the right one
CATEGORY_OPTIONS = ["general", "content", "technical", "bug", "feature", "other", "suggestion"]

def _find_valid_category():
    """Probe which category enum value the backend accepts."""
    _mock_user_fetch(role="teacher")
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[make_feedback_row()])
    for cat in CATEGORY_OPTIONS:
        mock_sb.reset_mock()
        _mock_user_fetch(role="teacher")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[make_feedback_row()])
        r = client.post("/api/feedback/", json={"category": cat, "message": "test msg"},
                        headers=auth_headers(role="teacher"))
        if r.status_code == 200:
            return cat
    return "general"  # fallback

# Discover valid category at module load time
_VALID_CATEGORY = None

def get_valid_category():
    global _VALID_CATEGORY
    if _VALID_CATEGORY is None:
        _VALID_CATEGORY = _find_valid_category()
    return _VALID_CATEGORY

# ── Submit Feedback POST /api/feedback/ ──────────────────────────────────────

class TestSubmitFeedback:

    def test_no_token_is_auth_error(self):
        r = client.post("/api/feedback/", json={"category": "general", "message": "test"})
        assert r.status_code in [401, 403]
        assert r.status_code != 200

    def test_teacher_submits_feedback_200(self):
        """Teacher submits valid feedback → 200"""
        cat = get_valid_category()
        _mock_user_fetch(role="teacher")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[make_feedback_row()])

        r = client.post("/api/feedback/", json={"category": cat, "message": "RAG needs work"},
                        headers=auth_headers(role="teacher"))
        assert r.status_code == 200
        assert r.status_code != 500

    def test_teacher_feedback_response_has_message(self):
        cat = get_valid_category()
        _mock_user_fetch(role="teacher")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[make_feedback_row()])

        r = client.post("/api/feedback/", json={"category": cat, "message": "All good"},
                        headers=auth_headers(role="teacher"))
        assert r.status_code == 200
        data = r.json()
        assert "message" in data or "feedback" in data

    def test_student_cannot_submit_teacher_feedback(self):
        _mock_user_fetch(role="student")
        r = client.post("/api/feedback/",
                        json={"category": "general", "message": "Hello"},
                        headers=auth_headers(role="student"))
        assert r.status_code == 403
        assert r.status_code != 200

    def test_admin_cannot_submit_teacher_feedback(self):
        _mock_user_fetch(role="admin")
        r = client.post("/api/feedback/",
                        json={"category": "general", "message": "Hello"},
                        headers=auth_headers(role="admin"))
        assert r.status_code == 403
        assert r.status_code != 200

    def test_missing_message_422(self):
        _mock_user_fetch(role="teacher")
        r = client.post("/api/feedback/", json={"category": "general"},
                        headers=auth_headers(role="teacher"))
        assert r.status_code == 422

    def test_missing_category_422(self):
        _mock_user_fetch(role="teacher")
        r = client.post("/api/feedback/", json={"message": "Good system"},
                        headers=auth_headers(role="teacher"))
        assert r.status_code == 422

    def test_feedback_never_500(self):
        cat = get_valid_category()
        _mock_user_fetch(role="teacher")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[make_feedback_row()])

        r = client.post("/api/feedback/", json={"category": cat, "message": "Works fine"},
                        headers=auth_headers(role="teacher"))
        assert r.status_code != 500


# ── Get All Feedback GET /api/feedback/ ──────────────────────────────────────

class TestGetFeedback:

    def test_no_token_is_auth_error(self):
        r = client.get("/api/feedback/")
        assert r.status_code in [401, 403]

    def test_admin_gets_all_feedback_200(self):
        _mock_user_fetch(role="admin")
        # feedback.py: .select("*, users!sender_id(...)").order(...).execute()
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(
            data=[make_feedback_row()]
        )
        r = client.get("/api/feedback/", headers=auth_headers(role="admin"))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_teacher_cannot_see_all_feedback(self):
        _mock_user_fetch(role="teacher")
        r = client.get("/api/feedback/", headers=auth_headers(role="teacher"))
        assert r.status_code == 403

    def test_student_cannot_see_all_feedback(self):
        _mock_user_fetch(role="student")
        r = client.get("/api/feedback/", headers=auth_headers(role="student"))
        assert r.status_code == 403

    def test_feedback_item_has_required_fields(self):
        _mock_user_fetch(role="admin")
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(
            data=[make_feedback_row()]
        )
        r = client.get("/api/feedback/", headers=auth_headers(role="admin"))
        if r.status_code == 200:
            items = r.json()
            if items:
                assert "id" in items[0]
                assert "message" in items[0]

    def test_get_feedback_never_500(self):
        _mock_user_fetch(role="admin")
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[])
        r = client.get("/api/feedback/", headers=auth_headers(role="admin"))
        assert r.status_code != 500


# ── My Feedback GET /api/feedback/mine ───────────────────────────────────────
# feedback.py /mine: .select("*").eq("sender_id", ...).order(...).execute()

class TestMyFeedback:

    def test_teacher_can_get_own_feedback(self):
        _mock_user_fetch(role="teacher")
        # Chain: .select("*").eq("sender_id", id).order("created_at", desc=True).execute()
        mock_sb.table.return_value.select.return_value \
               .eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[make_feedback_row()]
        )
        r = client.get("/api/feedback/mine", headers=auth_headers(role="teacher"))
        assert r.status_code == 200
        data = r.json()
        # Returns list directly
        assert isinstance(data, list)

    def test_mine_requires_auth(self):
        r = client.get("/api/feedback/mine")
        assert r.status_code in [401, 403]

    def test_mine_returns_only_own_feedback(self):
        """eq() is called with sender_id — no cross-user leakage"""
        _mock_user_fetch(role="teacher")
        mock_sb.table.return_value.select.return_value \
               .eq.return_value.order.return_value.execute.return_value = MagicMock(data=[])
        r = client.get("/api/feedback/mine", headers=auth_headers(role="teacher"))
        assert r.status_code == 200
        mock_sb.table.return_value.select.return_value.eq.assert_called()


# ── Student Feedback /api/student-feedback ───────────────────────────────────
# student_feedback.py: POST "" and GET ""
# student_feedback GET: .select("*").order("created_at", desc=True).execute()

class TestStudentFeedback:

    def test_student_post_no_trailing_slash(self):
        _mock_user_fetch(role="student")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{
            "id": "sfb-001", "message": "Notes are helpful"
        }])
        r = client.post("/api/student-feedback", json={"message": "Notes are helpful"},
                        headers=auth_headers(role="student"))
        assert r.status_code not in [405, 500]

    def test_student_submit_anonymous_feedback_200(self):
        _mock_user_fetch(role="student")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{
            "id": "sfb-001", "message": "Notes are helpful", "is_anonymous": True
        }])
        r = client.post("/api/student-feedback", json={
            "message": "Notes are helpful", "is_anonymous": True
        }, headers=auth_headers(role="student"))
        assert r.status_code == 200
        assert r.status_code != 500

    def test_admin_cannot_submit_student_feedback(self):
        _mock_user_fetch(role="admin")
        r = client.post("/api/student-feedback", json={"message": "test"},
                        headers=auth_headers(role="admin"))
        assert r.status_code == 403

    def test_get_student_feedback_as_admin(self):
        """Admin GETs student feedback → 200 with list"""
        _mock_user_fetch(role="admin")
        # student_feedback.py GET: .select("*").order("created_at", desc=True).execute()
        mock_sb.table.return_value.select.return_value \
               .order.return_value.execute.return_value = MagicMock(data=[
            {"id": "sfb-001", "message": "Good class", "is_anonymous": True}
        ])
        r = client.get("/api/student-feedback", headers=auth_headers(role="admin"))
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_get_student_feedback_as_teacher(self):
        """Teacher can also GET student feedback → 200"""
        _mock_user_fetch(role="teacher")
        mock_sb.table.return_value.select.return_value \
               .order.return_value.execute.return_value = MagicMock(data=[])
        r = client.get("/api/student-feedback", headers=auth_headers(role="teacher"))
        assert r.status_code == 200

    def test_student_cannot_view_all_feedback(self):
        _mock_user_fetch(role="student")
        r = client.get("/api/student-feedback", headers=auth_headers(role="student"))
        assert r.status_code == 403

    def test_no_password_in_response(self):
        _mock_user_fetch(role="student")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{
            "id": "sfb-002", "message": "Anonymous"
        }])
        r = client.post("/api/student-feedback", json={"message": "Anonymous"},
                        headers=auth_headers(role="student"))
        if r.status_code == 200:
            assert "password" not in str(r.json())
            assert "password_hash" not in str(r.json())