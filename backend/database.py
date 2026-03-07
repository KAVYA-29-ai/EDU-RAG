"""
Database Configuration — 100% Supabase (no local SQLite)
All tables (users, feedback, search_history, analytics, pdfs, pdf_chunks,
rag_embeddings) live in Supabase PostgreSQL.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")                       # anon key
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")   # service role key

supabase = None        # anon client
supabase_admin = None  # service-role client (bypasses RLS)


def init_supabase():
    """Create Supabase clients. The service-role client is used everywhere."""
    global supabase, supabase_admin
    url = SUPABASE_URL
    key = SUPABASE_KEY
    service_key = SUPABASE_SERVICE_KEY

    if url and service_key:
        try:
            from supabase_lite import create_client
            supabase_admin = create_client(url, service_key)
            supabase = create_client(url, key) if key else supabase_admin
            print("✅ Supabase connected (lite)")
        except Exception as e:
            print(f"⚠️  Supabase init error: {e}")
    else:
        print("⚠️  SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set — Supabase disabled")


def get_supabase():
    """Return the service-role Supabase client (or raise)."""
    if supabase_admin is None:
        raise RuntimeError(
            "Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env"
        )
    return supabase_admin


# ---------------------------------------------------------------------------
# Run on import
# ---------------------------------------------------------------------------
init_supabase()

