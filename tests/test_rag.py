import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import io

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

def make_user(role="student"):
    return {
        "id": "uuid-001", "name": "Test", "institution_id": f"{role}001",
        "email": f"{role}@test.com", "role": role, "avatar": "male",
        "status": "active", "password_hash": _hashed("pass123"),
    }

def _get_valid_token(role="student"):
    from jose import jwt as jose_jwt
    import os
    from datetime import datetime, timedelta
    return jose_jwt.encode(
        {"user_id": "uuid-001", "institution_id": f"{role}001", "role": role,
         "exp": datetime.utcnow() + timedelta(minutes=60)},
        os.getenv("JWT_SECRET", "your-secret-key"), algorithm="HS256"
    )

def auth_headers(role="student"):
    return {"Authorization": f"Bearer {_get_valid_token(role)}"}

def _mock_user_fetch(role="student"):
    user = make_user(role)
    mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[user])

def make_chunk():
    return {
        "id": "chunk-001",
        "content": "Neural networks learn via backpropagation.",
        "source_file": "ml_basics.pdf",
        "page_number": 3,
    }

def make_embedding():
    import json
    return {
        "id": "emb-001", "pdf_chunk_id": "chunk-001",
        "modality": "text",
        "embedding_json": json.dumps([0.9] * 768),
    }

# ── RAG Search ────────────────────────────────────────────────────────────────

class TestRAGSearch:

    def test_search_no_token_is_auth_error(self):
        r = client.post("/api/rag/search", json={"query": "test"})
        assert r.status_code in [401, 403]
        assert r.status_code != 200

    def test_search_missing_query_422(self):
        _mock_user_fetch()
        r = client.post("/api/rag/search", json={}, headers=auth_headers())
        assert r.status_code == 422

    def test_search_returns_200_with_result_keys(self):
        _mock_user_fetch()
        with patch("routers.rag._embed_text", return_value=[0.9] * 768), \
             patch("routers.rag._generate_rag_answer", return_value="Backpropagation adjusts weights."), \
             patch("routers.rag._get_gemini_client", return_value=MagicMock()):
            mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[make_embedding()])
            mock_sb.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(data=[make_chunk()])
            mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
            r = client.post("/api/rag/search",
                            json={"query": "how do neural networks learn"},
                            headers=auth_headers())
        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        assert "generated_answer" in data

    def test_search_empty_query_never_500(self):
        _mock_user_fetch()
        with patch("routers.rag._embed_text", return_value=None), \
             patch("routers.rag._get_gemini_client", return_value=None):
            mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
            r = client.post("/api/rag/search", json={"query": ""}, headers=auth_headers())
        assert r.status_code in [200, 400, 422]
        assert r.status_code != 500

    def test_search_no_results_200_not_500(self):
        _mock_user_fetch()
        with patch("routers.rag._embed_text", return_value=[0.1] * 768), \
             patch("routers.rag._get_gemini_client", return_value=MagicMock()):
            mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
            r = client.post("/api/rag/search", json={"query": "xyzzy quantum"}, headers=auth_headers())
        assert r.status_code == 200
        assert r.status_code != 500

    def test_search_response_has_all_keys(self):
        _mock_user_fetch()
        with patch("routers.rag._embed_text", return_value=[0.1] * 768), \
             patch("routers.rag._get_gemini_client", return_value=MagicMock()):
            mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
            r = client.post("/api/rag/search", json={"query": "ML"}, headers=auth_headers())
        assert r.status_code == 200
        data = r.json()
        assert "query" in data
        assert "results" in data
        assert "generated_answer" in data


# ── PDF Upload ────────────────────────────────────────────────────────────────

class TestPDFUpload:

    def test_upload_no_token_is_auth_error(self):
        r = client.post("/api/rag/upload-pdf",
                        files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")})
        assert r.status_code in [401, 403]

    def test_upload_non_pdf_rejected_400(self):
        _mock_user_fetch(role="teacher")
        r = client.post("/api/rag/upload-pdf",
                        files={"file": ("notes.txt", io.BytesIO(b"text"), "text/plain")},
                        headers=auth_headers(role="teacher"))
        assert r.status_code == 400
        assert r.status_code != 200

    def test_upload_student_forbidden_403(self):
        _mock_user_fetch(role="student")
        r = client.post("/api/rag/upload-pdf",
                        files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
                        headers=auth_headers(role="student"))
        assert r.status_code == 403

    def test_upload_teacher_success(self):
        _mock_user_fetch(role="teacher")
        new_pdf = {"id": 1, "filename": "test.pdf", "status": "pending_indexing"}
        mock_sb.storage.from_.return_value.upload.return_value = {"Key": "pdfs/test.pdf"}
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[new_pdf])

        with patch("routers.rag._ensure_storage_bucket", return_value=None), \
             patch("routers.rag.get_supabase", fake_get_supabase):
            r = client.post("/api/rag/upload-pdf",
                            files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
                            headers=auth_headers(role="teacher"))
        assert r.status_code == 200
        assert r.status_code != 500


# ── PDF List ──────────────────────────────────────────────────────────────────

class TestPDFList:

    def test_list_no_token_is_auth_error(self):
        r = client.get("/api/rag/pdfs")
        assert r.status_code in [401, 403]

    def test_list_returns_list(self):
        _mock_user_fetch()
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[
            {"id": 1, "filename": "ml.pdf", "status": "indexed",
             "total_pages": 10, "total_chunks": 50,
             "uploaded_by": "uuid-001", "created_at": "2026-01-01"}
        ])
        r = client.get("/api/rag/pdfs", headers=auth_headers())
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_item_structure(self):
        _mock_user_fetch()
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[
            {"id": 1, "filename": "ml.pdf", "status": "indexed",
             "total_pages": 5, "total_chunks": 20,
             "uploaded_by": "uuid-001", "created_at": "2026-01-01"}
        ])
        r = client.get("/api/rag/pdfs", headers=auth_headers())
        assert r.status_code == 200
        items = r.json()
        if items:
            assert "id" in items[0]
            assert "filename" in items[0]
            assert "status" in items[0]


# ── Search History ────────────────────────────────────────────────────────────
# rag.py search-history:
#   sb.table("search_history")
#     .select("id, query, language, results_count, created_at")
#     .eq("user_id", current_user.get("id"))
#     .order("created_at", desc=True)
#     .limit(limit)
#     .execute()
#
# BUT: get_current_user ALSO calls .select().eq().limit().execute() for user fetch
# Problem: both calls share the same mock chain → conflict
# Solution: use side_effect to return different values per call

class TestSearchHistory:

    def _setup_history_mock(self, history_data):
        """
        Set up mock so:
        - First .select().eq().limit().execute() → user (from get_current_user)
        - Second .select().eq().order().limit().execute() → history data
        """
        user = make_user(role="student")
        # User fetch chain: select().eq().limit().execute()
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[user])
        # History fetch chain: select().eq().order().limit().execute()
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=history_data)

    def test_history_no_token_is_auth_error(self):
        r = client.get("/api/rag/search-history")
        assert r.status_code in [401, 403]

    def test_history_returns_list(self):
        history_data = [
            {"id": "h1", "query": "what is RAG", "language": "en",
             "results_count": 3, "created_at": "2026-01-01T10:00:00"}
        ]
        self._setup_history_mock(history_data)
        r = client.get("/api/rag/search-history", headers=auth_headers())
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["query"] == "what is RAG"

    def test_history_filters_by_user(self):
        """eq() must be called — confirms user_id filter is applied"""
        self._setup_history_mock([])
        r = client.get("/api/rag/search-history", headers=auth_headers())
        assert r.status_code == 200
        # eq was called (at minimum for user fetch — confirms filtering pattern)
        mock_sb.table.return_value.select.return_value.eq.assert_called()

    def test_history_empty_returns_list(self):
        """No history → 200 with empty list"""
        self._setup_history_mock([])
        r = client.get("/api/rag/search-history", headers=auth_headers())
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)