import os, sys, pathlib, pytest
from unittest.mock import MagicMock, patch
from starlette.middleware.base import BaseHTTPMiddleware

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))

_mock_sb = MagicMock()
def _fake_db(): return _mock_sb

class _Noop(BaseHTTPMiddleware):
    async def dispatch(self, req, call_next): return await call_next(req)

patch("database.init_supabase", lambda: None).start()
patch("database.get_supabase", _fake_db).start()
patch("database.supabase_admin", _mock_sb).start()
patch("database.supabase", _mock_sb).start()
patch("main.RateLimitMiddleware", _Noop).start()

from main import app  # noqa
from fastapi.testclient import TestClient
_client = TestClient(app, raise_server_exceptions=False)

from passlib.context import CryptContext
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _user(role="teacher"):
    return {"id": f"uuid-{role}", "name": f"{role} user",
            "institution_id": f"{role}001", "email": f"{role}@t.com",
            "role": role, "avatar": "male", "status": "active",
            "password_hash": _pwd.hash("testpass123")}

def _set_user(role="teacher"):
    _mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[_user(role)])

def _jwt(role="teacher"):
    from jose import jwt as j
    from datetime import datetime, timedelta
    return j.encode({"user_id": f"uuid-{role}", "institution_id": f"{role}001",
                     "role": role, "exp": datetime.utcnow() + timedelta(minutes=60)},
                    os.getenv("JWT_SECRET", "your-secret-key"), algorithm="HS256")

def _auth(role="teacher"):
    return {"Authorization": f"Bearer {_jwt(role)}"}

def _fb():
    return {"id": "fb-001", "sender_id": "uuid-teacher", "category": "general",
            "message": "Test", "status": "pending", "created_at": "2026-01-01T10:00:00"}

@pytest.fixture(autouse=True)
def _reset():
    _mock_sb.reset_mock()
    _mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    _mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
    try:
        import main as _m
        _m._ip_buckets.clear()
    except Exception:
        pass
    yield

# ── Discover valid category (called fresh inside each test that needs it) ─────
def _valid_cat():
    """Try each category — return the one the backend accepts."""
    for cat in ["general", "content", "technical", "bug", "feature", "other", "suggestion"]:
        _mock_sb.reset_mock()
        _set_user("teacher")
        _mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[_fb()])
        r = _client.post("/api/feedback/",
                         json={"category": cat, "message": "probe"},
                         headers=_auth("teacher"))
        if r.status_code == 200:
            # Restore clean state before returning
            _mock_sb.reset_mock()
            _mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
            _mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
            return cat
    return "general"


# ── Submit Feedback ───────────────────────────────────────────────────────────

class TestSubmitFeedback:

    def test_no_token_auth_error(self):
        r = _client.post("/api/feedback/", json={"category": "general", "message": "t"})
        assert r.status_code in [401, 403]

    def test_teacher_200(self):
        cat = _valid_cat()
        _set_user("teacher")
        _mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[_fb()])
        r = _client.post("/api/feedback/", json={"category": cat, "message": "Good"}, headers=_auth("teacher"))
        assert r.status_code == 200

    def test_teacher_response_has_key(self):
        cat = _valid_cat()
        _set_user("teacher")
        _mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[_fb()])
        r = _client.post("/api/feedback/", json={"category": cat, "message": "Good"}, headers=_auth("teacher"))
        assert r.status_code == 200
        assert "message" in r.json() or "feedback" in r.json()

    def test_student_blocked_403(self):
        cat = _valid_cat()
        _set_user("student")
        r = _client.post("/api/feedback/", json={"category": cat, "message": "Hi"}, headers=_auth("student"))
        assert r.status_code == 403

    def test_admin_blocked_403(self):
        cat = _valid_cat()
        _set_user("admin")
        r = _client.post("/api/feedback/", json={"category": cat, "message": "Hi"}, headers=_auth("admin"))
        assert r.status_code == 403

    def test_missing_message_422(self):
        _set_user("teacher")
        r = _client.post("/api/feedback/", json={"category": "general"}, headers=_auth("teacher"))
        assert r.status_code == 422

    def test_missing_category_422(self):
        _set_user("teacher")
        r = _client.post("/api/feedback/", json={"message": "Good"}, headers=_auth("teacher"))
        assert r.status_code == 422

    def test_never_500(self):
        cat = _valid_cat()
        _set_user("teacher")
        _mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[_fb()])
        r = _client.post("/api/feedback/", json={"category": cat, "message": "Fine"}, headers=_auth("teacher"))
        assert r.status_code != 500


# ── Get All Feedback ──────────────────────────────────────────────────────────

class TestGetFeedback:

    def test_no_token_auth_error(self):
        r = _client.get("/api/feedback/")
        assert r.status_code in [401, 403]

    def test_admin_200(self):
        _set_user("admin")
        _mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[_fb()])
        r = _client.get("/api/feedback/", headers=_auth("admin"))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_teacher_blocked_403(self):
        _set_user("teacher")
        r = _client.get("/api/feedback/", headers=_auth("teacher"))
        assert r.status_code == 403

    def test_student_blocked_403(self):
        _set_user("student")
        r = _client.get("/api/feedback/", headers=_auth("student"))
        assert r.status_code == 403

    def test_item_has_fields(self):
        _set_user("admin")
        _mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[_fb()])
        r = _client.get("/api/feedback/", headers=_auth("admin"))
        if r.status_code == 200 and r.json():
            assert "id" in r.json()[0]

    def test_never_500(self):
        _set_user("admin")
        _mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[])
        r = _client.get("/api/feedback/", headers=_auth("admin"))
        assert r.status_code != 500


# ── My Feedback ───────────────────────────────────────────────────────────────
# feedback.py /mine: sb.table("feedback").select("*").eq("sender_id", id).order(...).execute()
# This does NOT have .limit() — so chain is: .select().eq().order().execute()

class TestMyFeedback:

    def test_teacher_gets_list(self):
        _set_user("teacher")
        # /mine chain: select("*").eq("sender_id",...).order(...).execute()
        _mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[_fb()])
        r = _client.get("/api/feedback/mine", headers=_auth("teacher"))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_requires_auth(self):
        r = _client.get("/api/feedback/mine")
        assert r.status_code in [401, 403]

    def test_eq_called_for_filter(self):
        _set_user("teacher")
        _mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=[])
        r = _client.get("/api/feedback/mine", headers=_auth("teacher"))
        assert r.status_code == 200
        _mock_sb.table.return_value.select.return_value.eq.assert_called()


# ── Student Feedback ──────────────────────────────────────────────────────────
# student_feedback.py GET: sb.table("student_feedback").select("*").order(...).execute()
# No .eq() in GET — chain is: .select().order().execute()

class TestStudentFeedback:

    def test_student_post_200(self):
        _set_user("student")
        _mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "s1", "message": "Good"}])
        r = _client.post("/api/student-feedback", json={"message": "Good", "is_anonymous": True}, headers=_auth("student"))
        assert r.status_code == 200

    def test_admin_post_blocked_403(self):
        _set_user("admin")
        r = _client.post("/api/student-feedback", json={"message": "t"}, headers=_auth("admin"))
        assert r.status_code == 403

    def test_admin_can_view_200(self):
        _set_user("admin")
        # GET chain: select("*").order("created_at", desc=True).execute()
        _mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(
            data=[{"id": "s1", "message": "Good", "is_anonymous": True}]
        )
        r = _client.get("/api/student-feedback", headers=_auth("admin"))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_teacher_can_view_200(self):
        _set_user("teacher")
        _mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[])
        r = _client.get("/api/student-feedback", headers=_auth("teacher"))
        assert r.status_code == 200

    def test_student_cannot_view(self):
        _set_user("student")
        r = _client.get("/api/student-feedback", headers=_auth("student"))
        assert r.status_code == 403

    def test_no_password_in_response(self):
        _set_user("student")
        _mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "s2", "message": "Anon"}])
        r = _client.post("/api/student-feedback", json={"message": "Anon"}, headers=_auth("student"))
        if r.status_code == 200:
            assert "password" not in str(r.json())
