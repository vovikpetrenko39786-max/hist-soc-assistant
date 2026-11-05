"""Server-to-server pilot token. Not end-user authentication.

Always fails closed if the shared token was not configured. Admin requests can
use the existing ADMIN_API_KEY as a separate authenticated principal.
"""
import secrets

from fastapi import Header, HTTPException

from app.core.config import get_settings


async def require_pilot_access(
    x_pilot_key: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
) -> None:
    settings = get_settings()
    if not settings.pilot_api_key:
        raise HTTPException(status_code=503, detail="Pilot API authentication is not configured")
    if x_pilot_key and secrets.compare_digest(x_pilot_key, settings.pilot_api_key):
        return
    if (settings.admin_api_key and x_admin_key and
            secrets.compare_digest(x_admin_key, settings.admin_api_key)):
        return
    raise HTTPException(status_code=401, detail="Authentication required")
