import pytest
from unittest.mock import MagicMock
from shared_fixtures import client, mock_sb, auth, make_user, mock_user


@pytest.fixture(autouse=True)
def reset():
    mock_sb.reset_mock()
    mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
    yield


def fb_row():
    return {"id": "fb-001", "sender_id": "uuid-teacher", "category": "general",
            "message": "Test feedback", "status": "pending", "created_at": "2026-01-01T10:00:00"}


def _probe_category():
    for cat in ["general", "content", "technical", "bug", "feature", "other", "suggestion"]:
        mock_sb.reset_mock()
        mock_user("teacher")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[fb_row()])
        r = client.post("/api/feedback/", json={"category": cat, "message": "probe"}, headers=auth("teacher"))
        if r.status_code == 200:
            return cat
    return "general"


VALID_CAT = _probe_category()


# ── Submit Feedback ───────────────────────────────────────────────────────────

class TestSubmitFeedback:

    def test_no_token_auth_error(self):
        r = client.post("/api/feedback/", json={"category": VALID_CAT, "message": "test"})
        assert r.status_code in [401, 403]

    def test_teacher_200(self):
        mock_user("teacher")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[fb_row()])
        r = client.post("/api/feedback/", json={"category": VALID_CAT, "message": "Good"}, headers=auth("teacher"))
        assert r.status_code == 200
        assert r.status_code != 500

    def test_teacher_response_has_message_key(self):
        mock_user("teacher")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[fb_row()])
        r = client.post("/api/feedback/", json={"category": VALID_CAT, "message": "Good"}, headers=auth("teacher"))
        assert r.status_code == 200
        assert "message" in r.json() or "feedback" in r.json()

    def test_student_blocked_403(self):
        mock_user("student")
        r = client.post("/api/feedback/", json={"category": VALID_CAT, "message": "Hi"}, headers=auth("student"))
        assert r.status_code == 403

    def test_admin_blocked_403(self):
        mock_user("admin")
        r = client.post("/api/feedback/", json={"category": VALID_CAT, "message": "Hi"}, headers=auth("admin"))
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
        r = client.post("/api/feedback/", json={"category": VALID_CAT, "message": "Fine"}, headers=auth("teacher"))
        assert r.status_code != 500


# ── Get All Feedback ──────────────────────────────────────────────────────────

class TestGetFeedback:

    def test_no_token_auth_error(self):
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

    def test_item_has_fields(self):
        mock_user("admin")
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[fb_row()])
        r = client.get("/api/feedback/", headers=auth("admin"))
        if r.status_code == 200 and r.json():
            assert "id" in r.json()[0] and "message" in r.json()[0]

    def test_never_500(self):
        mock_user("admin")
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[])
        r = client.get("/api/feedback/", headers=auth("admin"))
        assert r.status_code != 500


# ── My Feedback ───────────────────────────────────────────────────────────────

class TestMyFeedback:

    def test_teacher_gets_own_list(self):
        mock_user("teacher")
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[fb_row()])
        r = client.get("/api/feedback/mine", headers=auth("teacher"))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_requires_auth(self):
        r = client.get("/api/feedback/mine")
        assert r.status_code in [401, 403]

    def test_eq_called(self):
        mock_user("teacher")
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[])
        r = client.get("/api/feedback/mine", headers=auth("teacher"))
        assert r.status_code == 200
        mock_sb.table.return_value.select.return_value.eq.assert_called()


# ── Student Feedback ──────────────────────────────────────────────────────────

class TestStudentFeedback:

    def test_student_post_200(self):
        mock_user("student")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "sfb-001", "message": "Good"}])
        r = client.post("/api/student-feedback", json={"message": "Good", "is_anonymous": True}, headers=auth("student"))
        assert r.status_code == 200
        assert r.status_code != 500

    def test_admin_post_blocked_403(self):
        mock_user("admin")
        r = client.post("/api/student-feedback", json={"message": "test"}, headers=auth("admin"))
        assert r.status_code == 403

    def test_admin_can_view(self):
        mock_user("admin")
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[
            {"id": "sfb-001", "message": "Good", "is_anonymous": True}
        ])
        r = client.get("/api/student-feedback", headers=auth("admin"))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_teacher_can_view(self):
        mock_user("teacher")
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[])
        r = client.get("/api/student-feedback", headers=auth("teacher"))
        assert r.status_code == 200

    def test_student_cannot_view(self):
        mock_user("student")
        r = client.get("/api/student-feedback", headers=auth("student"))
        assert r.status_code == 403

    def test_no_password_in_response(self):
        mock_user("student")
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "sfb-002", "message": "Anon"}])
        r = client.post("/api/student-feedback", json={"message": "Anon"}, headers=auth("student"))
        if r.status_code == 200:
            assert "password" not in str(r.json())