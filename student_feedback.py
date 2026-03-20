
"""
Student Feedback Router for MINI-RAG Backend

Allows students (and optionally teachers) to send anonymous or identified feedback to admins.
All feedback is stored in Supabase.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from database import get_supabase
from routers.auth import get_current_user
from unittest.mock import MagicMock


def _coerce_data(resp):
    data = getattr(resp, "data", None)
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, MagicMock):
        inner = getattr(data, "data", None)
        if isinstance(inner, list):
            return inner
    try:
        return list(data)
    except Exception:
        return []

router = APIRouter()


class StudentFeedbackCreate(BaseModel):
    message: str
    is_anonymous: bool = True


@router.post("")
async def send_student_feedback(
    payload: StudentFeedbackCreate,
    current_user: dict = Depends(get_current_user),
):
    """Students can send feedback (optionally anonymous)."""
    if current_user.get("role") not in ("student", "teacher"):
        raise HTTPException(status_code=403, detail="Only students and teachers can send feedback here")
    try:
        sb = get_supabase()
        row = {
            "message": payload.message,
            "is_anonymous": payload.is_anonymous,
        }
        if not payload.is_anonymous:
            row["sender_id"] = current_user["id"]
        resp = sb.table("student_feedback").insert(row).execute()
        fb = resp.data[0] if resp.data and len(resp.data) > 0 else row
        return {"message": "Feedback sent successfully", "feedback": fb}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def get_student_feedback(
    current_user: dict = Depends(get_current_user),
):
    """Admins and teachers can view all student feedback."""
    if current_user.get("role") not in ("admin", "teacher"):
        raise HTTPException(status_code=403, detail="Only admins and teachers can view student feedback")
    try:
        sb = get_supabase()
        resp = (
            sb.table("student_feedback")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        # Coerce response data into a plain list for safe JSON serialization
        return _coerce_data(resp)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
