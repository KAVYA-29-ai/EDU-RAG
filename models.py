
"""
Pydantic Models for MINI-RAG Backend

Defines all data models, enums, and schemas used for request and response validation
in the MINI-RAG FastAPI backend. Includes user, feedback, and other domain models.
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

# Enums
class UserRole(str, Enum):
    student = "student"
    teacher = "teacher"
    admin = "admin"

class FeedbackCategory(str, Enum):
    system = "system"
    feature = "feature"
    content = "content"
    rag = "rag"
    student = "student"
    other = "other"

class FeedbackStatus(str, Enum):
    pending = "pending"
    responded = "responded"
    archived = "archived"

# Auth Models
class UserRegister(BaseModel):
    name: str
    institution_id: str
    email: Optional[str] = None
    password: str
    avatar: str = "male"
    role: UserRole = UserRole.student

class UserLogin(BaseModel):
    institution_id: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict
    requires_verification: bool = False
    message: Optional[str] = None

# User Models
class UserBase(BaseModel):
    id: Optional[int] = None
    name: str
    institution_id: str
    email: Optional[str] = None
    role: UserRole
    avatar: str
    status: str = "active"
    created_at: Optional[datetime] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    avatar: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    name: str
    institution_id: str
    email: Optional[str] = None
    role: UserRole
    avatar: str
    status: str
    created_at: datetime

# Feedback Models
class FeedbackCreate(BaseModel):
    category: FeedbackCategory
    message: str

class FeedbackResponse(BaseModel):
    id: int
    sender_id: int
    sender_name: str
    sender_institution_id: str
    sender_avatar: str
    category: FeedbackCategory
    message: str
    status: FeedbackStatus
    admin_response: Optional[str] = None
    created_at: datetime

class FeedbackUpdate(BaseModel):
    status: Optional[FeedbackStatus] = None
    admin_response: Optional[str] = None

# RAG Models
class RAGQuery(BaseModel):
    query: str
    language: str = "english"

class RAGResult(BaseModel):
    id: int
    content: str
    source: str
    relevance_score: float
    page_number: Optional[int] = None

class RAGResponse(BaseModel):
    query: str
    results: List[RAGResult]
    total_results: int
    response_time_ms: int

class SearchHistory(BaseModel):
    id: int
    user_id: int
    query: str
    language: str
    results_count: int
    created_at: datetime

# Analytics Models
class AnalyticsSummary(BaseModel):
    total_queries: int
    total_pdfs: int
    rag_accuracy: float
    avg_response_time: float
    active_users: int

class TopicAnalysis(BaseModel):
    topic: str
    search_count: int
    difficulty: str

class UsageByRole(BaseModel):
    role: str
    percentage: float
    count: int

class LanguageUsage(BaseModel):
    language: str
    percentage: float
    count: int
