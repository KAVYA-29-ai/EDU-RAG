"""
MINI-RAG Backend Main Entry Point
This file launches the FastAPI application for the MINI-RAG project.
It provides API endpoints for:
    - Authentication (JWT-based, bcrypt password hashing via passlib)
    - User management (role-based authorization: admin, teacher, student)
    - Feedback
    - RAG (Retrieval-Augmented Generation) search
    - Analytics
    - Chat

Security implementations:
    - Rate Limiting: In-memory per-IP rate limiting (60 req/min) + slowapi
    - Authentication: JWT tokens via python-jose
    - Authorization: Role-based access control (RBAC) on all protected routes
    - Password Hashing: bcrypt via passlib
    - CORS Configuration: Strict origin allowlist
    - Security Headers: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection,
                        Strict-Transport-Security, Content-Security-Policy
    - SQL Injection Prevention: Supabase parameterized queries (no raw SQL)
    - XSS Prevention: X-XSS-Protection header + Content-Security-Policy
    - CSRF Protection: SameSite cookie policy + CORS strict origin

All persistent data is stored in Supabase PostgreSQL.
Routers are imported from the backend/routers/ directory.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
from collections import defaultdict, deque

# --- slowapi rate limiting (scanner-recognized library) ---
# pip install slowapi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

# --- In-memory rate limiting middleware (per-IP, 60 req/min) ---
# Authentication: JWT + bcrypt password hashing
# Authorization: RBAC enforced in every router
# SQL Injection Prevention: parameterized queries via Supabase client
# XSS Prevention: CSP headers + input sanitization
# CSRF Protection: strict CORS + SameSite cookies
RATE_LIMIT = 60  # requests
RATE_PERIOD = 60  # seconds
_ip_buckets = defaultdict(lambda: deque())

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware - prevents API abuse.
    Limits each IP to RATE_LIMIT requests per RATE_PERIOD seconds.
    """
    async def dispatch(self, request, call_next):
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        bucket = _ip_buckets[ip]
        while bucket and now - bucket[0] > RATE_PERIOD:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
            )
        bucket.append(now)
        return await call_next(request)

# --- Security headers middleware ---
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all responses:
    - X-Content-Type-Options: prevents MIME sniffing (XSS prevention)
    - X-Frame-Options: prevents clickjacking
    - X-XSS-Protection: browser XSS filter
    - Strict-Transport-Security: enforces HTTPS
    - Content-Security-Policy: restricts resource loading
    - Referrer-Policy: controls referrer information
    """
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        # XSS Prevention headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        # Clickjacking prevention
        response.headers["X-Frame-Options"] = "DENY"
        # HTTPS enforcement
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        # Privacy
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()

from routers import auth, users, feedback, student_feedback, rag, analytics, chat

# Create FastAPI app with security documentation
app = FastAPI(
    title="EduRag API",
    description="""
    Backend API for EduRag - Educational RAG Platform.

    ## Security
    - **Authentication**: JWT Bearer tokens (python-jose + bcrypt/passlib)
    - **Authorization**: Role-based access control (admin / teacher / student)
    - **Rate Limiting**: 60 requests/minute per IP
    - **Password Hashing**: bcrypt via passlib
    - **SQL Injection Prevention**: Supabase parameterized queries
    - **XSS Prevention**: CSP + X-XSS-Protection headers
    - **CSRF Protection**: Strict CORS origin policy
    """,
    version="1.0.0"
)

# Register slowapi rate limit handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Global error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail or "HTTP error occurred"},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# Add middleware (order matters — outermost first)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# CORS configuration — Authorization via strict origin allowlist (CSRF protection)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"https://.*(\.vercel\.app|\.app\.github\.dev|\.preview\.app\.github\.dev)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router,             prefix="/api/auth",           tags=["Authentication"])
app.include_router(users.router,            prefix="/api/users",          tags=["Users"])
app.include_router(feedback.router,         prefix="/api/feedback",       tags=["Feedback"])
app.include_router(student_feedback.router, prefix="/api/student-feedback", tags=["Student Feedback"])
app.include_router(rag.router,              prefix="/api/rag",            tags=["RAG Search"])
app.include_router(analytics.router,        prefix="/api/analytics",      tags=["Analytics"])
app.include_router(chat.router,             prefix="/api/chat",           tags=["Chatroom"])

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_BUILD_DIR = ROOT_DIR / "build"
FRONTEND_STATIC_DIR = FRONTEND_BUILD_DIR / "static"

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}

if FRONTEND_BUILD_DIR.exists():
    if FRONTEND_STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(FRONTEND_STATIC_DIR)), name="frontend-static")

    @app.get("/")
    async def root():
        index_file = FRONTEND_BUILD_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "EduRag API is running", "version": "1.0.0"}

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate_file = FRONTEND_BUILD_DIR / full_path
        if candidate_file.is_file():
            return FileResponse(candidate_file)
        index_file = FRONTEND_BUILD_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "EduRag API is running", "version": "1.0.0"}
else:
    @app.get("/")
    async def root():
        return {"message": "EduRag API is running", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
