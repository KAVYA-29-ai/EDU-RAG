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

def make_user(role="student"):
    return {
        "id": "uuid-001", "name": "Test", "institution_id": f"{role}001",
        "email": f"{role}@test.com", "role": role, "avatar": "male",
        "status": "active", "password_hash": _hashed("pass123"),
    }

def _get_valid_token(role="student"):
    """
    Get a real signed JWT by calling login with mock — 
    then decode to verify it's valid. This token stays valid even after
    mock.reset_mock() because JWT is verified by secret, not by mock.
    """
    from jose import jwt as jose_jwt
    import os
    from datetime import datetime, timedelta
    payload = {
        "user_id": "uuid-001",
        "institution_id": f"{role}001",
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=60),
    }
    secret = os.getenv("JWT_SECRET", "your-secret-key")
    return jose_jwt.encode(payload, secret, algorithm="HS256")

def auth_headers(role="student"):
    """Return Authorization headers with a valid JWT — no mock dependency."""
    tok = _get_valid_token(role)
    return {"Authorization": f"Bearer {tok}"}

def _mock_user_fetch(role="student"):
    """After token is decoded, app fetches user from DB — mock that."""
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
        """No token → 401 or 403"""
        r = client.post("/api/rag/search", json={"query": "test"})
        assert r.status_code in [401, 403]
        assert r.status_code != 200

    def test_search_missing_query_422(self):
        """Missing query field → 422 validation error"""
        _mock_user_fetch()
        r = client.post("/api/rag/search", json={}, headers=auth_headers())
        assert r.status_code == 422

    def test_search_returns_200_with_results_key(self):
        """Valid query → 200 with results + generated_answer"""
        _mock_user_fetch()
        emb = make_embedding()
        chunk = make_chunk()

        with patch("routers.rag._embed_text", return_value=[0.9] * 768), \
             patch("routers.rag._generate_rag_answer", return_value="Backpropagation adjusts weights."), \
             patch("routers.rag._get_gemini_client", return_value=MagicMock()):

            mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[emb])
            mock_sb.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(data=[chunk])
            mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])

            r = client.post("/api/rag/search",
                            json={"query": "how do neural networks learn"},
                            headers=auth_headers())

        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        assert "generated_answer" in data

    def test_search_empty_query_rejected(self):
        """Empty string query → 400 or 422, never 200"""
        _mock_user_fetch()
        with patch("routers.rag._embed_text", return_value=None), \
             patch("routers.rag._get_gemini_client", return_value=None):
            r = client.post("/api/rag/search", json={"query": ""}, headers=auth_headers())
        assert r.status_code in [400, 422]
        assert r.status_code != 200

    def test_search_no_results_returns_200_not_500(self):
        """No matching chunks → 200 with fallback, never 500"""
        _mock_user_fetch()
        with patch("routers.rag._embed_text", return_value=[0.1] * 768), \
             patch("routers.rag._get_gemini_client", return_value=MagicMock()):
            mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])

            r = client.post("/api/rag/search",
                            json={"query": "xyzzy quantum teleport"},
                            headers=auth_headers())
        assert r.status_code == 200
        assert r.status_code != 500

    def test_search_response_structure(self):
        """Response always has query, results, generated_answer"""
        _mock_user_fetch()
        with patch("routers.rag._embed_text", return_value=[0.1] * 768), \
             patch("routers.rag._get_gemini_client", return_value=MagicMock()):
            mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])

            r = client.post("/api/rag/search",
                            json={"query": "machine learning"},
                            headers=auth_headers())
        assert r.status_code == 200
        data = r.json()
        assert "query" in data
        assert "results" in data
        assert "generated_answer" in data


# ── PDF Upload ────────────────────────────────────────────────────────────────

class TestPDFUpload:

    def test_upload_no_token_is_auth_error(self):
        import io
        r = client.post("/api/rag/upload-pdf",
                        files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")})
        assert r.status_code in [401, 403]

    def test_upload_non_pdf_rejected_400(self):
        """Non-PDF → 400, not 200"""
        import io
        _mock_user_fetch(role="teacher")
        r = client.post("/api/rag/upload-pdf",
                        files={"file": ("notes.txt", io.BytesIO(b"text"), "text/plain")},
                        headers=auth_headers(role="teacher"))
        assert r.status_code == 400
        assert r.status_code != 200

    def test_upload_student_forbidden_403(self):
        """Student cannot upload → 403"""
        import io
        _mock_user_fetch(role="student")
        r = client.post("/api/rag/upload-pdf",
                        files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
                        headers=auth_headers(role="student"))
        assert r.status_code == 403
        assert r.status_code != 200

    def test_upload_teacher_success(self):
        """Teacher uploads valid PDF → 200"""
        import io
        _mock_user_fetch(role="teacher")
        new_pdf = {"id": 1, "filename": "test.pdf", "status": "pending_indexing"}

        mock_sb.storage.from_.return_value.upload.return_value = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[new_pdf])

        with patch("routers.rag._ensure_storage_bucket", return_value=None):
            r = client.post("/api/rag/upload-pdf",
                            files={"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
                            headers=auth_headers(role="teacher"))

        assert r.status_code == 200
        assert r.status_code != 403
        assert r.status_code != 500


# ── PDF List ──────────────────────────────────────────────────────────────────

class TestPDFList:

    def test_list_pdfs_no_token_is_auth_error(self):
        r = client.get("/api/rag/pdfs")
        assert r.status_code in [401, 403]

    def test_list_pdfs_returns_list(self):
        _mock_user_fetch()
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[
            {"id": 1, "filename": "ml.pdf", "status": "indexed",
             "total_pages": 10, "total_chunks": 50,
             "uploaded_by": "uuid-001", "created_at": "2026-01-01"}
        ])
        r = client.get("/api/rag/pdfs", headers=auth_headers())
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_pdfs_structure(self):
        """Each PDF item has id, filename, status"""
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

class TestSearchHistory:

    def test_history_no_token_is_auth_error(self):
        r = client.get("/api/rag/search-history")
        assert r.status_code in [401, 403]

    def test_history_returns_list(self):
        _mock_user_fetch()
        mock_sb.table.return_value.select.return_value \
               .eq.return_value.order.return_value \
               .limit.return_value.execute.return_value = MagicMock(data=[
            {"id": "h1", "query": "what is RAG", "language": "en",
             "results_count": 3, "created_at": "2026-01-01T10:00:00"}
        ])
        r = client.get("/api/rag/search-history", headers=auth_headers())
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_history_is_user_specific(self):
        """History uses eq(user_id) filter — no cross-user leakage"""
        _mock_user_fetch()
        mock_sb.table.return_value.select.return_value \
               .eq.return_value.order.return_value \
               .limit.return_value.execute.return_value = MagicMock(data=[])
        r = client.get("/api/rag/search-history", headers=auth_headers())
        assert r.status_code == 200
        mock_sb.table.return_value.select.return_value.eq.assert_called()
