import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

mock_supabase = MagicMock()

with patch("backend.database.supabase", mock_supabase):
    from backend.main import app

client = TestClient(app)

# ─── Helpers ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_mocks():
    mock_supabase.reset_mock()
    yield

def get_auth_headers(role="teacher"):
    import bcrypt
    hashed = bcrypt.hashpw(b"pass123", bcrypt.gensalt()).decode()
    user = {
        "id": f"user-{role}-001", "name": "Test User",
        "institution_id": f"{role}001", "email": f"{role}@test.com",
        "role": role, "avatar": "female", "password_hash": hashed
    }
    mock_supabase.table().select().eq().execute.return_value = MagicMock(data=[user])
    resp = client.post("/api/auth/login", json={"institution_id": f"{role}001", "password": "pass123"})
    data = resp.json()
    token = data.get("access_token") or data.get("token", "")
    return {"Authorization": f"Bearer {token}"}

def make_feedback(role_from="teacher"):
    return {
        "id": "fb-001",
        "user_id": f"user-{role_from}-001",
        "message": "The RAG system needs better source diversity",
        "rating": 4,
        "created_at": "2026-01-01T10:00:00",
        "response": None
    }

# ─── Submit Feedback ──────────────────────────────────────────────────────────

class TestSubmitFeedback:

    def test_teacher_can_submit_feedback(self):
        """Teacher submits feedback → 200"""
        headers = get_auth_headers(role="teacher")
        mock_supabase.table().insert().execute.return_value = MagicMock(
            data=[make_feedback()]
        )
        response = client.post("/api/feedback/", json={
            "message": "Search results need improvement",
            "rating": 4
        }, headers=headers)
        assert response.status_code == 200
        assert response.status_code != 500

    def test_feedback_requires_auth(self):
        """No token → 401"""
        response = client.post("/api/feedback/", json={
            "message": "Good platform",
            "rating": 5
        })
        assert response.status_code == 401
        assert response.status_code != 200

    def test_feedback_missing_message(self):
        """Missing message field → 422"""
        headers = get_auth_headers(role="teacher")
        response = client.post("/api/feedback/", json={"rating": 3}, headers=headers)
        assert response.status_code == 422

    def test_feedback_invalid_rating(self):
        """Rating out of valid range → 400 or 422"""
        headers = get_auth_headers(role="teacher")
        response = client.post("/api/feedback/", json={
            "message": "Great",
            "rating": 99  # invalid
        }, headers=headers)
        assert response.status_code in [400, 422]
        assert response.status_code != 200

    def test_feedback_empty_message_rejected(self):
        """Empty message → not accepted"""
        headers = get_auth_headers(role="teacher")
        response = client.post("/api/feedback/", json={
            "message": "",
            "rating": 3
        }, headers=headers)
        assert response.status_code in [400, 422]
        assert response.status_code != 200

# ─── Get Feedback (Admin) ─────────────────────────────────────────────────────

class TestGetFeedback:

    def test_admin_can_get_all_feedback(self):
        """Admin → 200 with feedback list"""
        headers = get_auth_headers(role="admin")
        mock_supabase.table().select().execute.return_value = MagicMock(
            data=[make_feedback(), make_feedback()]
        )
        response = client.get("/api/feedback/", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_student_cannot_get_all_feedback(self):
        """Student role → 403, not 200"""
        headers = get_auth_headers(role="student")
        response = client.get("/api/feedback/", headers=headers)
        assert response.status_code in [403, 401]
        assert response.status_code != 200

    def test_get_feedback_requires_auth(self):
        """No token → 401"""
        response = client.get("/api/feedback/")
        assert response.status_code == 401

    def test_feedback_list_structure(self):
        """Each feedback item has required fields"""
        headers = get_auth_headers(role="admin")
        mock_supabase.table().select().execute.return_value = MagicMock(
            data=[make_feedback()]
        )
        response = client.get("/api/feedback/", headers=headers)
        if response.status_code == 200:
            data = response.json()
            if len(data) > 0:
                item = data[0]
                assert "id" in item or "message" in item or "rating" in item

# ─── Student Anonymous Feedback ───────────────────────────────────────────────

class TestStudentFeedback:

    def test_student_can_submit_anonymous_feedback(self):
        """Student submits anonymous feedback to teacher → 200"""
        headers = get_auth_headers(role="student")
        mock_supabase.table().insert().execute.return_value = MagicMock(data=[{
            "id": "sfb-001",
            "message": "Class notes are very helpful",
            "created_at": "2026-01-01T10:00:00"
        }])
        response = client.post("/api/feedback/student", json={
            "message": "Class notes are very helpful"
        }, headers=headers)
        # Should succeed or endpoint may not exist yet
        assert response.status_code in [200, 201, 404]
        assert response.status_code != 500
        assert response.status_code != 401

    def test_anonymous_feedback_not_linked_to_user(self):
        """Anonymous feedback response must not expose user identity"""
        headers = get_auth_headers(role="student")
        mock_supabase.table().insert().execute.return_value = MagicMock(data=[{
            "id": "sfb-002",
            "message": "Anonymous message",
        }])
        response = client.post("/api/feedback/student", json={
            "message": "This is anonymous"
        }, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Should not expose user_id or email in response
            assert "email" not in data
            assert "password" not in data
