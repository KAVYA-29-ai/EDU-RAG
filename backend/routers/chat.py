
"""
Chat Router for MINI-RAG Backend

Provides endpoints for student chatroom functionality. Messages are auto-deleted after a configurable timer.
Includes message creation and retrieval endpoints. Only students can send messages.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List
from datetime import datetime
import os

from database import get_supabase
from core.rbac import require_roles
from services.chat_service import (
    cleanup_old_messages,
    create_message,
    delete_own_message,
    list_recent_messages,
)

router = APIRouter()

CHAT_MESSAGE_LIFETIME = int(os.getenv('CHAT_MESSAGE_LIFETIME', 60))  # seconds

class ChatMessageCreate(BaseModel):
    message: str

class ChatMessageOut(BaseModel):
    id: int
    sender_id: int
    sender_name: str
    message: str
    created_at: datetime

@router.post("/messages", response_model=ChatMessageOut)
async def send_message(
    payload: ChatMessageCreate,
    current_user: dict = Depends(require_roles("student")),
):
    try:
        sb = get_supabase()
        msg = create_message(
            sb,
            sender_id=current_user["id"],
            sender_name=current_user["name"],
            message=payload.message,
        )
        return msg
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/messages", response_model=List[ChatMessageOut])
async def get_messages(current_user: dict = Depends(require_roles("student"))):
    try:
        sb = get_supabase()
        return list_recent_messages(sb, lifetime_hours=1)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/messages/{message_id}")
async def delete_message(message_id: int, current_user: dict = Depends(require_roles("student"))):
    """
    Allow a user to delete their own chat message by ID.
    """
    try:
        sb = get_supabase()
        ok, detail = delete_own_message(sb, message_id=message_id, owner_id=current_user["id"])
        if not ok:
            raise HTTPException(status_code=403, detail=detail)
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/messages/cleanup")
async def cleanup_old_messages():
    """
    Delete chat messages older than 1 hour.
    """
    try:
        sb = get_supabase()
        deleted = cleanup_old_messages(sb, lifetime_hours=1)
        return {"deleted": deleted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        return {"deleted": resp.count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
