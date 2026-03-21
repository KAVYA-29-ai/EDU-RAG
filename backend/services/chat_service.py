"""Service-layer operations for chat messages."""

from datetime import datetime, timedelta


def create_message(supabase, *, sender_id, sender_name, message: str):
    row = {
        "sender_id": sender_id,
        "sender_name": sender_name,
        "message": message,
    }
    resp = supabase.table("chat_messages").insert(row).execute()
    return resp.data[0]


def list_recent_messages(supabase, *, lifetime_hours: int = 1):
    cutoff = datetime.utcnow() - timedelta(hours=lifetime_hours)
    resp = (
        supabase.table("chat_messages")
        .select("*")
        .gte("created_at", cutoff.isoformat())
        .order("created_at", desc=False)
        .execute()
    )
    return resp.data or []


def delete_own_message(supabase, *, message_id: int, owner_id):
    resp = supabase.table("chat_messages").select("*").eq("id", message_id).execute()
    if not resp.data:
        return False, "Message not found"
    if str(resp.data[0].get("sender_id")) != str(owner_id):
        return False, "You can only delete your own messages."
    supabase.table("chat_messages").delete().eq("id", message_id).execute()
    return True, "deleted"


def cleanup_old_messages(supabase, *, lifetime_hours: int = 1):
    cutoff = datetime.utcnow() - timedelta(hours=lifetime_hours)
    resp = supabase.table("chat_messages").delete().lt("created_at", cutoff.isoformat()).execute()
    return resp.count
