"""RBAC dependencies shared across routers.

This module centralizes role checks so routers can use consistent,
declarative access policies instead of manual if/raise blocks.
"""

from typing import Iterable

from fastapi import Depends, HTTPException

from routers.auth import get_current_user


def _normalize_roles(roles: Iterable[str]) -> set[str]:
    return {str(role).strip().lower() for role in roles if str(role).strip()}


def require_roles(*allowed_roles: str):
    """Return a dependency that allows only the specified roles."""
    allowed = _normalize_roles(allowed_roles)

    async def dependency(current_user: dict = Depends(get_current_user)):
        user_role = str(current_user.get("role", "")).lower()
        if user_role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user

    return dependency


def require_self_or_roles(*allowed_roles: str):
    """Return a checker callable for endpoints that allow self or admin-like roles."""
    allowed = _normalize_roles(allowed_roles)

    def checker(current_user: dict, target_user_id):
        user_role = str(current_user.get("role", "")).lower()
        is_allowed_role = user_role in allowed
        is_self = str(current_user.get("id")) == str(target_user_id)
        if not is_allowed_role and not is_self:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

    return checker
