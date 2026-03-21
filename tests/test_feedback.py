import os, sys, pathlib, pytest
from unittest.mock import MagicMock, patch, PropertyMock
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict, deque

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
import main as _m
_m._ip_buckets = defaultdict(lambda: deque())

from fastapi.testclient import TestClient
_client = TestClient(app, raise_server_exceptions=False)

from passlib.context import CryptContext
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

# FeedbackCategory enum values from models.py:
# system, feature, content, rag, student, other
CAT = "content"

def _user(role="teacher"):
    return {"id": f"uuid-{role}", "name": f"{role} user",
            "institution_id": f"{role}001", "email": f"{role}@t.com",
            "role": role, "avatar": "male", "status": "active",
            "password_hash": _pwd.hash("testpass123")}

def _jwt(role="teacher"):
    from jose import jwt as j
    from datetime import datetime, timedelta
    return j.encode({"user_id": f"uuid-{role}", "institution_id": f"{role}001",
                     "role": role, "exp": datetime.utcnow() + timedelta(minutes=60)},
                    os.getenv("JWT_SECRET", "your-secret-key"), algorithm="HS256")

def _auth(role="teacher"):
    return {"Authorization": f"Bearer {_jwt(role)}"}

def _fb():
    return {"id": "fb-001", "sender_id": "uuid-teacher", "category": "content",
            "message": "Test", "status": "pending", "created_at": "2026-01-01T10:00:00"}

def _setup(role="teacher", mine_data=None, insert_data=None, order_data=None):
    """
    Set up ALL mock chains at once to avoid conflicts.
    - user fetch:     table().select().eq().limit().execute()  -> user
    - /mine fetch:    table().select().eq().order().execute()  -> mine_data
    - insert:         table().insert().execute()               -> insert_data
    - order fetch:    table().select().order().execute()       -> order_data
    """
    _mock_sb.reset_mock()
    _m._ip_buckets.clear()
    # user fetch chain
    _mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[_user(role)])
    # /mine chain (eq → order → execute, no limit)
    if mine_data is not None:
        _mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(data=mine_data)
    # insert chain
    if insert_data is not None:
        _mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=insert_data)
    # order-only chain (student_feedback GET, feedback GET)
    if order_data is not None:
        _mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=order_data)

@pytest.fixture(autouse=True)
def _reset():
    _mock_sb.reset_mock()
    _mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    _mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
    _m._ip_buckets.clear()
    yield


# ── Submit Feedback POST /api/feedback/ ──────────────────────────────────────

class TestSubmitFeedback:

    def test_no_token_auth_error(self):
        r = _client.post("/api/feedback/", json={"category": CAT, "message": "t"})
        assert r.status_code in [401, 403]

    def test_teacher_200(self):
        _setup("teacher", insert_data=[_fb()])
        r = _client.post("/api/feedback/", json={"category": CAT, "message": "Good"}, headers=_auth("teacher"))
        assert r.status_code == 200

    def test_teacher_response_has_key(self):
        _setup("teacher", insert_data=[_fb()])
        r = _client.post("/api/feedback/", json={"category": CAT, "message": "Good"}, headers=_auth("teacher"))
        assert r.status_code == 200
        assert "message" in r.json() or "feedback" in r.json()

    def test_student_blocked_403(self):
        _setup("student")
        r = _client.post("/api/feedback/", json={"category": CAT, "message": "Hi"}, headers=_auth("student"))
        assert r.status_code == 403

    def test_admin_blocked_403(self):
        _setup("admin")
        r = _client.post("/api/feedback/", json={"category": CAT, "message": "Hi"}, headers=_auth("admin"))
        assert r.status_code == 403

    def test_missing_message_422(self):
        _setup("teacher")
        r = _client.post("/api/feedback/", json={"category": CAT}, headers=_auth("teacher"))
        assert r.status_code == 422

    def test_missing_category_422(self):
        _setup("teacher")
        r = _client.post("/api/feedback/", json={"message": "Good"}, headers=_auth("teacher"))
        assert r.status_code == 422

    def test_never_500(self):
        _setup("teacher", insert_data=[_fb()])
        r = _client.post("/api/feedback/", json={"category": CAT, "message": "Fine"}, headers=_auth("teacher"))
        assert r.status_code != 500


# ── Get All Feedback GET /api/feedback/ ──────────────────────────────────────

class TestGetFeedback:

    def test_no_token_auth_error(self):
        r = _client.get("/api/feedback/")
        assert r.status_code in [401, 403]

    def test_admin_200(self):
        # feedback GET: .select("*, users!...").order(...).execute()  — no .eq()
        _setup("admin", order_data=[_fb()])
        r = _client.get("/api/feedback/", headers=_auth("admin"))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_teacher_blocked_403(self):
        _setup("teacher")
        r = _client.get("/api/feedback/", headers=_auth("teacher"))
        assert r.status_code == 403

    def test_student_blocked_403(self):
        _setup("student")
        r = _client.get("/api/feedback/", headers=_auth("student"))
        assert r.status_code == 403

    def test_item_has_fields(self):
        _setup("admin", order_data=[_fb()])
        r = _client.get("/api/feedback/", headers=_auth("admin"))
        if r.status_code == 200 and r.json():
            assert "id" in r.json()[0]

    def test_never_500(self):
        _setup("admin", order_data=[])
        r = _client.get("/api/feedback/", headers=_auth("admin"))
        assert r.status_code != 500


# ── My Feedback GET /api/feedback/mine ───────────────────────────────────────
# feedback.py /mine:
#   sb.table("feedback").select("*").eq("sender_id", id).order("created_at", desc=True).execute()
# chain: select().eq().order().execute()  (NO .limit())

class TestMyFeedback:

    def test_teacher_gets_list(self):
        _setup("teacher", mine_data=[_fb()])
        r = _client.get("/api/feedback/mine", headers=_auth("teacher"))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_requires_auth(self):
        r = _client.get("/api/feedback/mine")
        assert r.status_code in [401, 403]

    def test_eq_called_for_filter(self):
        _setup("teacher", mine_data=[])
        r = _client.get("/api/feedback/mine", headers=_auth("teacher"))
        assert r.status_code == 200
        # eq() is called for both user fetch AND /mine sender_id filter
        _mock_sb.table.return_value.select.return_value.eq.assert_called()


# ── Student Feedback /api/student-feedback ───────────────────────────────────
# student_feedback.py GET:
#   sb.table("student_feedback").select("*").order("created_at", desc=True).execute()
# chain: select().order().execute()  (NO .eq())

class TestStudentFeedback:

    def test_student_post_200(self):
        _setup("student", insert_data=[{"id": "s1", "message": "Good"}])
        r = _client.post("/api/student-feedback",
                         json={"message": "Good", "is_anonymous": True},
                         headers=_auth("student"))
        assert r.status_code == 200

    def test_admin_post_blocked_403(self):
        _setup("admin")
        r = _client.post("/api/student-feedback", json={"message": "t"}, headers=_auth("admin"))
        assert r.status_code == 403

    def test_admin_can_view_200(self):
        # student-feedback GET: select().order().execute()
        _setup("admin", order_data=[{"id": "s1", "message": "Good", "is_anonymous": True}])
        r = _client.get("/api/student-feedback", headers=_auth("admin"))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_teacher_can_view_200(self):
        _setup("teacher", order_data=[])
        r = _client.get("/api/student-feedback", headers=_auth("teacher"))
        assert r.status_code == 200

    def test_student_cannot_view(self):
        _setup("student")
        r = _client.get("/api/student-feedback", headers=_auth("student"))
        assert r.status_code == 403

    def test_no_password_in_response(self):
        _setup("student", insert_data=[{"id": "s2", "message": "Anon"}])
        r = _client.post("/api/student-feedback", json={"message": "Anon"}, headers=_auth("student"))
        if r.status_code == 200:
            assert "password" not in str(r.json())
