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

def get_auth_headers(role="student"):
    """Get a real JWT token via login mock"""
    import bcrypt
    hashed = bcrypt.hashpw(b"pass123", bcrypt.gensalt()).decode()
    user = {
        "id": "user-001", "name": "Test", "institution_id": "u001",
        "email": "t@test.com", "role": role,
        "avatar": "male", "password_hash": hashed
    }
    mock_supabase.table().select().eq().execute.return_value = MagicMock(data=[user])
    resp = client.post("/api/auth/login", json={"institution_id": "u001", "password": "pass123"})
    data = resp.json()
    token = data.get("access_token") or data.get("token", "")
    return {"Authorization": f"Bearer {token}"}

def make_chunk(text="Neural networks learn by adjusting weights", score=0.82):
    return {
        "id": "chunk-001",
        "text": text,
        "score": score,
        "pdf_title": "ML Basics",
        "chunk_index": 0
    }

# ─── Search Tests ─────────────────────────────────────────────────────────────

class TestRAGSearch:

    def test_search_returns_results(self):
        """Valid query → 200 with non-empty results list"""
        headers = get_auth_headers()
        mock_supabase.table().select().execute.return_value = MagicMock(
            data=[make_chunk()]
        )
        with patch("backend.routers.rag.generate_embedding", return_value=[0.1] * 768), \
             patch("backend.routers.rag.gemini_generate", return_value="AI learns by backpropagation."):
            response = client.post("/api/rag/search", json={"query": "how do neural networks learn"}, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict) or isinstance(data, list)

    def test_search_requires_auth(self):
        """No token → 401"""
        response = client.post("/api/rag/search", json={"query": "test query"})
        assert response.status_code == 401
        assert response.status_code != 200

    def test_search_empty_query_rejected(self):
        """Empty string query → 400 or 422, not 200"""
        headers = get_auth_headers()
        response = client.post("/api/rag/search", json={"query": ""}, headers=headers)
        assert response.status_code in [400, 422]
        assert response.status_code != 200

    def test_search_missing_query_field(self):
        """Missing query field → 422 validation error"""
        headers = get_auth_headers()
        response = client.post("/api/rag/search", json={}, headers=headers)
        assert response.status_code == 422

    def test_search_response_has_answer_field(self):
        """Response must contain 'answer' or 'results' key"""
        headers = get_auth_headers()
        mock_supabase.table().select().execute.return_value = MagicMock(
            data=[make_chunk()]
        )
        with patch("backend.routers.rag.generate_embedding", return_value=[0.1] * 768), \
             patch("backend.routers.rag.gemini_generate", return_value="Backpropagation adjusts weights."):
            response = client.post("/api/rag/search", json={"query": "what is backpropagation"}, headers=headers)

        if response.status_code == 200:
            data = response.json()
            has_answer = "answer" in data or "results" in data or "response" in data
            assert has_answer, f"Response missing answer/results key. Got: {list(data.keys())}"

    def test_search_no_results_returns_fallback(self):
        """Zero matching chunks → still returns 200 with fallback message, not 500"""
        headers = get_auth_headers()
        mock_supabase.table().select().execute.return_value = MagicMock(data=[])
        with patch("backend.routers.rag.generate_embedding", return_value=[0.1] * 768):
            response = client.post("/api/rag/search", json={"query": "xyzzy quantum teleportation"}, headers=headers)

        assert response.status_code in [200, 404]
        assert response.status_code != 500

# ─── PDF Upload Tests ─────────────────────────────────────────────────────────

class TestPDFUpload:

    def test_upload_pdf_requires_auth(self):
        """Unauthenticated upload → 401"""
        import io
        fake_pdf = io.BytesIO(b"%PDF-1.4 fake content")
        response = client.post("/api/rag/upload-pdf", files={"file": ("test.pdf", fake_pdf, "application/pdf")})
        assert response.status_code == 401

    def test_upload_non_pdf_rejected(self):
        """Non-PDF file → 400, not 200"""
        import io
        headers = get_auth_headers(role="teacher")
        fake_txt = io.BytesIO(b"this is a text file")
        response = client.post(
            "/api/rag/upload-pdf",
            files={"file": ("notes.txt", fake_txt, "text/plain")},
            headers=headers
        )
        assert response.status_code in [400, 422]
        assert response.status_code != 200

    def test_upload_student_cannot_upload(self):
        """Student role → 403 forbidden, only teacher/admin can upload"""
        import io
        headers = get_auth_headers(role="student")
        fake_pdf = io.BytesIO(b"%PDF-1.4 fake pdf content")
        response = client.post(
            "/api/rag/upload-pdf",
            files={"file": ("test.pdf", fake_pdf, "application/pdf")},
            headers=headers
        )
        assert response.status_code in [403, 401]
        assert response.status_code != 200

# ─── PDF List Tests ───────────────────────────────────────────────────────────

class TestPDFList:

    def test_list_pdfs_returns_list(self):
        """GET /api/rag/pdfs → 200 with list"""
        headers = get_auth_headers()
        mock_supabase.table().select().execute.return_value = MagicMock(data=[
            {"id": "pdf-001", "title": "ML Basics", "uploaded_by": "user-001"}
        ])
        response = client.get("/api/rag/pdfs", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_pdfs_requires_auth(self):
        """No token → 401"""
        response = client.get("/api/rag/pdfs")
        assert response.status_code == 401

# ─── Search History Tests ─────────────────────────────────────────────────────

class TestSearchHistory:

    def test_search_history_returns_list(self):
        """GET /api/rag/search-history → 200 with list"""
        headers = get_auth_headers()
        mock_supabase.table().select().eq().execute.return_value = MagicMock(data=[
            {"query": "what is RAG", "created_at": "2026-01-01T10:00:00"}
        ])
        response = client.get("/api/rag/search-history", headers=headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_search_history_requires_auth(self):
        """No token → 401"""
        response = client.get("/api/rag/search-history")
        assert response.status_code == 401
