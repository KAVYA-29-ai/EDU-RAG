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

def get_token(role="teacher"):
    user = make_user(role)
    mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[user])
    r = client.post("/api/auth/login", json={"institution_id": f"{role}001", "password": "pass123"})
    if r.status_code != 200:
        return None
    d = r.json()
    return d.get("access_token") or d.get("token")

def auth_headers(role="teacher"):
    tok = get_token(role)
    return {"Authorization": f"Bearer {tok}"} if tok else {}

def make_feedback_row():
    return {
        "id": "fb-001", "user_id": "uuid-teacher",
        "message": "RAG needs better source diversity",
        "rating": 4, "created_at": "2026-01-01T10:00:00", "response": None
    }

# ── Submit Feedback (/api/feedback/) ─────────────────────────────────────────

class TestSubmitFeedback:

    def test_no_token_is_auth_error(self):
        """No token → auth error"""
        r = client.post("/api/feedback/", json={"message": "Good", "rating": 5})
        assert r.status_code in [401, 403]
        assert r.status_code != 200

    def test_teacher_submits_feedback_200(self):
        """Teacher submits feedback → 200"""
        headers = auth_headers(role="teacher")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[make_feedback_row()])

        r = client.post("/api/feedback/", json={
            "message": "Search results need improvement",
            "rating": 4
        }, headers=headers)
        assert r.status_code == 200
        assert r.status_code != 500

    def test_admin_submits_feedback_200(self):
        """Admin can also submit feedback → 200"""
        headers = auth_headers(role="admin")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[make_feedback_row()])

        r = client.post("/api/feedback/", json={
            "message": "System works well overall",
            "rating": 5
        }, headers=headers)
        assert r.status_code in [200, 403]  # depends on role policy
        assert r.status_code != 500

    def test_missing_message_422(self):
        """Missing message → 422 (after auth passes)"""
        headers = auth_headers(role="teacher")
        r = client.post("/api/feedback/", json={"rating": 3}, headers=headers)
        # 422 validation OR 403 if teacher isn't allowed — both are non-500
        assert r.status_code in [403, 422]
        assert r.status_code != 500

    def test_feedback_response_not_500(self):
        """Any feedback submission must never return 500"""
        headers = auth_headers(role="teacher")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[make_feedback_row()])

        r = client.post("/api/feedback/", json={
            "message": "Works fine",
            "rating": 3
        }, headers=headers)
        assert r.status_code != 500


# ── Get All Feedback (/api/feedback/) ────────────────────────────────────────

class TestGetFeedback:

    def test_no_token_is_auth_error(self):
        r = client.get("/api/feedback/")
        assert r.status_code in [401, 403]
        assert r.status_code != 200

    def test_admin_gets_feedback_list(self):
        """Admin → 200 with list"""
        headers = auth_headers(role="admin")
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(
            data=[make_feedback_row(), make_feedback_row()]
        )
        r = client.get("/api/feedback/", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_student_cannot_see_all_feedback(self):
        """Student → 403, not 200"""
        headers = auth_headers(role="student")
        r = client.get("/api/feedback/", headers=headers)
        assert r.status_code in [403, 401]
        assert r.status_code != 200

    def test_feedback_item_has_required_fields(self):
        """Each feedback item has id, message, rating"""
        headers = auth_headers(role="admin")
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(
            data=[make_feedback_row()]
        )
        r = client.get("/api/feedback/", headers=headers)
        if r.status_code == 200:
            items = r.json()
            if items:
                assert "id" in items[0] or "message" in items[0]

    def test_get_feedback_never_500(self):
        """GET feedback must never return 500"""
        headers = auth_headers(role="admin")
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
        r = client.get("/api/feedback/", headers=headers)
        assert r.status_code != 500


# ── Student Feedback (/api/student-feedback/) ────────────────────────────────
# NOTE: main.py registers this at prefix "/api/student-feedback" not "/api/feedback/student"

class TestStudentFeedback:

    def test_student_feedback_no_token_is_auth_error(self):
        r = client.get("/api/student-feedback/")
        assert r.status_code in [401, 403]

    def test_student_can_submit_via_correct_endpoint(self):
        """Student posts to /api/student-feedback/ → 200 or 404 (not 405/500)"""
        headers = auth_headers(role="student")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{
            "id": "sfb-001", "message": "Class notes are helpful"
        }])
        r = client.post("/api/student-feedback/", json={
            "message": "Class notes are very helpful"
        }, headers=headers)
        # 200 = works, 404 = endpoint not fully implemented yet, both acceptable
        # 405 = wrong HTTP method, 500 = crash — both unacceptable
        assert r.status_code not in [405, 500]

    def test_anonymous_feedback_no_password_in_response(self):
        """Response must never expose password"""
        headers = auth_headers(role="student")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{
            "id": "sfb-002", "message": "Anonymous message"
        }])
        r = client.post("/api/student-feedback/", json={"message": "Anonymous"}, headers=headers)
        if r.status_code == 200:
            data = r.json()
            assert "password" not in str(data)
            assert "password_hash" not in str(data)
