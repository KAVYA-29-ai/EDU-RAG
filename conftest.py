import pytest
from unittest.mock import MagicMock
import backend.database as db_mod
import backend.routers.auth as auth_mod
import backend.routers.feedback as feedback_mod
import backend.routers.rag as rag_mod
import backend.routers.student_feedback as sfb_mod


@pytest.fixture(autouse=True)
def mock_supabase(monkeypatch):
    """Provide a shared MagicMock Supabase client for tests.

    Tests can customize `mock_sb.table().select().execute.return_value` as needed.
    """
    mock_sb = MagicMock(name="mock_sb")
    # Ensure get_supabase() in database returns this mock
    monkeypatch.setattr(db_mod, "get_supabase", lambda: mock_sb)
    yield mock_sb


@pytest.fixture
def auth_headers():
    def _headers(role="teacher", user_id=1):
        return {"Authorization": f"Bearer faketoken-{role}-{user_id}"}
    return _headers


@pytest.fixture
def make_feedback_row():
    def _make(id_val="fb-001", sender_id=1, message="Good class"):
        return {
            "id": id_val,
            "sender_id": sender_id,
            "message": message,
            "category": "feature",
            "status": "pending",
            "created_at": "2026-01-01T00:00:00",
        }
    return _make


@pytest.fixture
def _mock_user_fetch(monkeypatch):
    """Monkeypatch the `get_current_user` dependency across routers to return a test user."""
    def _inner(role="teacher", user_id=1, name="Test User", institution_id="inst1"):
        user = {
            "id": user_id,
            "name": name,
            "institution_id": institution_id,
            "role": role,
            "avatar": "male",
        }

        async def _mock_get_current_user(*args, **kwargs):
            return user

        # Patch auth module and routers that imported get_current_user at import time
        monkeypatch.setattr(auth_mod, "get_current_user", _mock_get_current_user)
        monkeypatch.setattr(feedback_mod, "get_current_user", _mock_get_current_user)
        monkeypatch.setattr(rag_mod, "get_current_user", _mock_get_current_user)
        monkeypatch.setattr(sfb_mod, "get_current_user", _mock_get_current_user)

        return user

    return _inner
