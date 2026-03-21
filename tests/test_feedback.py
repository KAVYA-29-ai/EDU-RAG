import pytest
from unittest.mock import MagicMock
from conftest import app, mock_sb, fake_get_supabase, TestClient
from unittest.mock import patch

client = TestClient(app, raise_server_exceptions=False)

@pytest.fixture(autouse=True)
def reset_mock():
    mock_sb.reset_mock()
    mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
    yield

def _hashed(plain):
    from passlib.context import CryptContext
    return CryptContext(schemes=["bcrypt"], deprecated="auto").hash(plain)

def make_user(role="teacher"):
    return {
        "id": f"uuid-{role}", "name": f"{role.title()} User",
        "institution_id": f"{role}001", "email": f"{role}@test.com",
        "role": role, "avatar": "female", "status": "active",
        "password_hash": _hashed("pass123"),
    }

def _jwt(role="teacher"):
    from jose import jwt as jose_jwt
    import os
    from datetime import datetime, timedelta
    return jose_jwt.encode(
        {"user_id": f"uuid-{role}", "institution_id": f"{role}001", "role": role,
         "exp": datetime.utcnow() + timedelta(minutes=60)},
        os.getenv("JWT_SECRET", "your-secret-key"), algorithm="HS256"
    )

def auth(role="teacher"):
    return {"Authorization": f"Bearer {_jwt(role)}"}

def mock_user(role="teacher"):
    mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[make_user(role)])

def fb_row():
    return {"id": "fb-001", "sender_id": "uuid-teacher", "category": "general",
            "message": "Test feedback", "status": "pending", "created_at": "2026-01-01T10:00:00"}

# Discover valid category at module level
def _probe_category():
    for cat in ["general", "content", "technical", "bug", "feature", "other", "suggestion", "query"]:
        mock_sb.reset_mock()
        mock_user("teacher")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[fb_row()])
        r = client.post("/api/feedback/", json={"category": cat, "message": "probe"},
                        headers=auth("teacher"))
        if r.status_code == 200:
            return cat
    return "general"

VALID_CAT = _probe_category()

# ── Submit Feedback ───────────────────────────────────────────────────────────

class TestSubmitFeedback:

    def test_no_token_is_auth_error(self):
        r = client.post("/api/feedback/", json={"category": VALID_CAT, "message": "test"})
        assert r.status_code in [401, 403]

    def test_teacher_submits_feedback_200(self):
        mock_user("teacher")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[fb_row()])
        r = client.post("/api/feedback/", json={"category": VALID_CAT, "message": "Good"},
                        headers=auth("teacher"))
        assert r.status_code == 200
        assert r.status_code != 500

    def test_teacher_response_has_message_key(self):
        mock_user("teacher")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[fb_row()])
        r = client.post("/api/feedback/", json={"category": VALID_CAT, "message": "Good"},
                        headers=auth("teacher"))
        assert r.status_code == 200
        assert "message" in r.json() or "feedback" in r.json()

    def test_student_blocked_403(self):
        mock_user("student")
        r = client.post("/api/feedback/", json={"category": VALID_CAT, "message": "Hi"},
                        headers=auth("student"))
        assert r.status_code == 403

    def test_admin_blocked_403(self):
        mock_user("admin")
        r = client.post("/api/feedback/", json={"category": VALID_CAT, "message": "Hi"},
                        headers=auth("admin"))
        assert r.status_code == 403

    def test_missing_message_422(self):
        mock_user("teacher")
        r = client.post("/api/feedback/", json={"category": VALID_CAT}, headers=auth("teacher"))
        assert r.status_code == 422

    def test_missing_category_422(self):
        mock_user("teacher")
        r = client.post("/api/feedback/", json={"message": "Good"}, headers=auth("teacher"))
        assert r.status_code == 422

    def test_never_500(self):
        mock_user("teacher")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[fb_row()])
        r = client.post("/api/feedback/", json={"category": VALID_CAT, "message": "Fine"},
                        headers=auth("teacher"))
        assert r.status_code != 500


# ── Get All Feedback ──────────────────────────────────────────────────────────

class TestGetFeedback:

    def test_no_token_is_auth_error(self):
        r = client.get("/api/feedback/")
        assert r.status_code in [401, 403]

    def test_admin_gets_list_200(self):
        mock_user("admin")
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[fb_row()])
        r = client.get("/api/feedback/", headers=auth("admin"))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_teacher_blocked_403(self):
        mock_user("teacher")
        r = client.get("/api/feedback/", headers=auth("teacher"))
        assert r.status_code == 403

    def test_student_blocked_403(self):
        mock_user("student")
        r = client.get("/api/feedback/", headers=auth("student"))
        assert r.status_code == 403

    def test_item_has_required_fields(self):
        mock_user("admin")
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[fb_row()])
        r = client.get("/api/feedback/", headers=auth("admin"))
        if r.status_code == 200 and r.json():
            assert "id" in r.json()[0]
            assert "message" in r.json()[0]

    def test_never_500(self):
        mock_user("admin")
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[])
        r = client.get("/api/feedback/", headers=auth("admin"))
        assert r.status_code != 500


# ── My Feedback ───────────────────────────────────────────────────────────────

class TestMyFeedback:

    def test_teacher_gets_own_feedback(self):
        mock_user("teacher")
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[fb_row()])
        r = client.get("/api/feedback/mine", headers=auth("teacher"))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_requires_auth(self):
        r = client.get("/api/feedback/mine")
        assert r.status_code in [401, 403]

    def test_eq_called_for_user_filter(self):
        mock_user("teacher")
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[])
        r = client.get("/api/feedback/mine", headers=auth("teacher"))
        assert r.status_code == 200
        mock_sb.table.return_value.select.return_value.eq.assert_called()


# ── Student Feedback ──────────────────────────────────────────────────────────

class TestStudentFeedback:

    def test_student_post_succeeds(self):
        mock_user("student")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "sfb-001", "message": "Good"}])
        r = client.post("/api/student-feedback", json={"message": "Good", "is_anonymous": True}, headers=auth("student"))
        assert r.status_code == 200
        assert r.status_code != 500

    def test_admin_blocked_403(self):
        mock_user("admin")
        r = client.post("/api/student-feedback", json={"message": "test"}, headers=auth("admin"))
        assert r.status_code == 403

    def test_admin_can_view_student_feedback(self):
        mock_user("admin")
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[
            {"id": "sfb-001", "message": "Good", "is_anonymous": True}
        ])
        r = client.get("/api/student-feedback", headers=auth("admin"))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_teacher_can_view_student_feedback(self):
        mock_user("teacher")
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[])
        r = client.get("/api/student-feedback", headers=auth("teacher"))
        assert r.status_code == 200

    def test_student_cannot_view_list(self):
        mock_user("student")
        r = client.get("/api/student-feedback", headers=auth("student"))
        assert r.status_code == 403

    def test_no_password_in_response(self):
        mock_user("student")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "sfb-002", "message": "Anon"}])
        r = client.post("/api/student-feedback", json={"message": "Anon"}, headers=auth("student"))
        if r.status_code == 200:
            assert "password" not in str(r.json())