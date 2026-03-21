import pytest
import io
from unittest.mock import MagicMock, patch
from shared_fixtures import client, mock_sb, auth, make_user, mock_user, fake_get_supabase


@pytest.fixture(autouse=True)
def reset():
    mock_sb.reset_mock()
    mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
    yield


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

    def test_search_200(self):
        mock_user()
        with patch("routers.rag._embed_text", return_value=[0.9]*768), \
             patch("routers.rag._generate_rag_answer", return_value="Answer."), \
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

    def test_no_results_200(self):
        mock_user()
        with patch("routers.rag._embed_text", return_value=[0.1]*768), \
             patch("routers.rag._get_gemini_client", return_value=MagicMock()):
            mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
            r = client.post("/api/rag/search", json={"query": "xyzzy"}, headers=auth())
        assert r.status_code == 200
        assert r.status_code != 500

    def test_response_keys(self):
        mock_user()
        with patch("routers.rag._embed_text", return_value=[0.1]*768), \
             patch("routers.rag._get_gemini_client", return_value=MagicMock()):
            mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.select.return_value.ilike.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
            r = client.post("/api/rag/search", json={"query": "ML"}, headers=auth())
        assert r.status_code == 200
        for key in ["query", "results", "generated_answer"]:
            assert key in r.json()


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

    def test_teacher_upload_200(self):
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
             "total_pages": 10, "total_chunks": 50, "uploaded_by": "uuid-student", "created_at": "2026-01-01"}
        ])
        r = client.get("/api/rag/pdfs", headers=auth())
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_item_structure(self):
        mock_user()
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(data=[
            {"id": 1, "filename": "ml.pdf", "status": "indexed",
             "total_pages": 5, "total_chunks": 20, "uploaded_by": "uuid-student", "created_at": "2026-01-01"}
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
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[make_user()])
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=data)

    def test_no_token_auth_error(self):
        r = client.get("/api/rag/search-history")
        assert r.status_code in [401, 403]

    def test_returns_list(self):
        self._setup([{"id": "h1", "query": "what is RAG", "language": "en", "results_count": 3, "created_at": "2026-01-01T10:00:00"}])
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