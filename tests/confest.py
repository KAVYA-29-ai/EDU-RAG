import pytest
from unittest.mock import MagicMock, patch
 
# Global Supabase mock — applied before any app import
@pytest.fixture(scope="session", autouse=True)
def mock_supabase_globally():
    with patch("backend.database.supabase", MagicMock()):
        yield
 
# Shared environment variables for testing
import os
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-pytest")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("SUPABASE_URL", "https://mock.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "mock-key")
os.environ.setdefault("GEMINI_API_KEY", "mock-gemini-key")
