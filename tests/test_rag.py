import pytest
import io
from unittest.mock import MagicMock, patch
from conftest import app, mock_sb, fake_get_supabase, TestClient

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

def make_user(role="student"):
    return {
        "id": "uuid-001", "name": "Test", "institution_id": f"{role}001",
        "email": f"{role}@test.com", "role": role, "avatar": "male",
        "status": "active", "password_hash": _hashed("pass123"),
    }

def _jwt(role="student"):
    from jose import jwt as jose_jwt
    import os
    from datetime import datetime, timedelta
    return jose_jwt.encode(
        {"user_id": "uuid-001", "institution_id": f"{role}001", "role": role,
         "exp": datetime.utcnow() + timedelta(minutes=60)},
        os.getenv("JWT_SECRET", "your-secret-key"), algorithm="HS256"
    )

def auth(role="student"):
    return {"Authorization": f"Bearer {_jwt(role)}"}

def mock_user(role="student"):
    mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[make_user(role)])

def make_chunk():
    return {"id": "chunk-001", "content": "Neural nets learn via backprop.", "source_file": "ml.pdf", "page_number": 3}

def make_emb():
    import json
    return {"id": "emb-001", "pdf_chunk_id": "chunk-001", "modality": "text", "embedding_json": json.dumps([0.9] * 768)}


# ── RAG Search ────────────────────────────────────────────────────────────────

class TestRAGSearch:

    def test_no_token_auth_error(self):
        r = client.post("/api/rag/search", json={"query": "test"})
        assert r.status_code in [401, 403]

    def test_missing_query_422(self):
        mock_user()
        r = client.post("/api/rag/search", json={}, headers=auth())
        assert r.status_code == 422

    def test_search_returns_200(self):
        mock_user()
        with patch("routers.rag._embed_text", return_value=[0.9]*768), \
             patch("routers.rag._generate_rag_answer", return_value="Answer here."), \
             patch("routers.rag._get_gemini_client", return_value=MagicMock()):
            mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[make_emb()])
            mock_sb.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(data=[make_chunk()])
            mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
            r = client.post("/api/rag/search", json={"query": "neural networks"}, headers=auth())
        assert r.status_code == 200
        assert "results" in r.json()
        assert "generated_answer" in r.json()

    def test_empty_query_never_500(self):
        mock_user()
        with patch("routers.rag._embed_text", return_value=None), \
             patch("routers.rag._get_gemini_client", return_value=None):
            mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
            r = client.post("/api/rag/search", json={"query": ""}, headers=auth())
        assert r.status_code in [200, 400, 422]
        assert r.status_code != 500

    def test_no_results_200_not_500(self):
        mock_user()
        with patch("routers.rag._embed_text", return_value=[0.1]*768), \
             patch("routers.rag._get_gemini_client", return_value=MagicMock()):
            mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
            r = client.post("/api/rag/search", json={"query": "xyzzy"}, headers=auth())
        assert r.status_code == 200
        assert r.status_code != 500

    def test_response_has_all_keys(self):
        mock_user()
        with patch("routers.rag._embed_text", return_value=[0.1]*768), \
             patch("routers.rag._get_gemini_client", return_value=MagicMock()):
            mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
            r = client.post("/api/rag/search", json={"query": "ML"}, headers=auth())
        assert r.status_code == 200
        data = r.json()
        for key in ["query", "results", "generated_answer"]:
            assert key in data


# ── PDF Upload ────────────────────────────────────────────────────────────────

class TestPDFUpload:

    def test_no_token_auth_error(self):
        r = client.post("/api/rag/upload-pdf", files={"file": ("t.pdf", io.BytesIO(b"%PDF"), "application/pdf")})
        assert r.status_code in [401, 403]

    def test_non_pdf_400(self):
        mock_user("teacher")
        r = client.post("/api/rag/upload-pdf",
                        files={"file": ("notes.txt", io.BytesIO(b"text"), "text/plain")},
                        headers=auth("teacher"))
        assert r.status_code == 400

    def test_student_forbidden_403(self):
        mock_user("student")
        r = client.post("/api/rag/upload-pdf",
                        files={"file": ("t.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
                        headers=auth("student"))
        assert r.status_code == 403

    def test_teacher_upload_success(self):
        mock_user("teacher")
        new_pdf = {"id": 1, "filename": "test.pdf", "status": "pending_indexing"}
        mock_sb.storage.from_.return_value.upload.return_value = {"Key": "pdfs/test.pdf"}
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[new_pdf])
        with patch("routers.rag._ensure_storage_bucket", return_value=None), \
             patch("routers.rag.get_supabase", fake_get_supabase):
            r = client.post("/api/rag/upload-pdf",
                            files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
                            headers=auth("teacher"))
        assert r.status_code == 200
        assert r.status_code != 500


# ── PDF List ──────────────────────────────────────────────────────────────────

class TestPDFList:

    def test_no_token_auth_error(self):
        r = client.get("/api/rag/pdfs")
        assert r.status_code in [401, 403]

    def test_returns_list(self):
        mock_user()
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[
            {"id": 1, "filename": "ml.pdf", "status": "indexed",
             "total_pages": 10, "total_chunks": 50, "uploaded_by": "uuid-001", "created_at": "2026-01-01"}
        ])
        r = client.get("/api/rag/pdfs", headers=auth())
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_item_structure(self):
        mock_user()
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[
            {"id": 1, "filename": "ml.pdf", "status": "indexed",
             "total_pages": 5, "total_chunks": 20, "uploaded_by": "uuid-001", "created_at": "2026-01-01"}
        ])
        r = client.get("/api/rag/pdfs", headers=auth())
        assert r.status_code == 200
        items = r.json()
        if items:
            assert "id" in items[0] and "filename" in items[0] and "status" in items[0]


# ── Search History ────────────────────────────────────────────────────────────

class TestSearchHistory:

    def _setup(self, data):
        mock_user()
        # user fetch: .select().eq().limit().execute()
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[make_user()])
        # history fetch: .select().eq().order().limit().execute()
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=data)

    def test_no_token_auth_error(self):
        r = client.get("/api/rag/search-history")
        assert r.status_code in [401, 403]

    def test_returns_list(self):
        hist = [{"id": "h1", "query": "what is RAG", "language": "en", "results_count": 3, "created_at": "2026-01-01T10:00:00"}]
        self._setup(hist)
        r = client.get("/api/rag/search-history", headers=auth())
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert r.json()[0]["query"] == "what is RAG"

    def test_filters_by_user(self):
        self._setup([])
        r = client.get("/api/rag/search-history", headers=auth())
        assert r.status_code == 200
        mock_sb.table.return_value.select.return_value.eq.assert_called()

    def test_empty_returns_list(self):
        self._setup([])
        r = client.get("/api/rag/search-history", headers=auth())
        assert r.status_code == 200
        assert isinstance(r.json(), list)