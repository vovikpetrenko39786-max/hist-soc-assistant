"""Authentication and scoped authorization for the closed Telegram pilot."""
from __future__ import annotations

import json
import re
import secrets
import uuid
from dataclasses import dataclass

from fastapi import Header, HTTPException, Request

from app.core.config import get_settings
from app.core.telegram_access import parse_allowed_user_ids


@dataclass(frozen=True)
class PilotPrincipal:
    role: str
    external_id: str | None = None


def is_strong_shared_key(value: str | None) -> bool:
    """Require roughly 256 bits of generated token material, not a passphrase."""
    return bool(
        value
        and len(value) >= 43
        and not any(character.isspace() for character in value)
        and len(set(value)) >= 12
    )


def parse_course_bindings(raw: str | None) -> dict[int, frozenset[uuid.UUID]]:
    """Parse only the authorization-relevant part of trusted bot bindings."""
    if not raw or not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid course bindings JSON") from exc
    if not isinstance(payload, dict) or len(payload) > 100:
        raise ValueError("Course bindings must map up to 100 users")
    result: dict[int, frozenset[uuid.UUID]] = {}
    for raw_user_id, courses in payload.items():
        if (
            not isinstance(raw_user_id, str)
            or not re.fullmatch(r"[1-9][0-9]*", raw_user_id)
            or not isinstance(courses, dict)
            or len(courses) > 32
        ):
            raise ValueError("Invalid course binding user")
        identifiers: set[uuid.UUID] = set()
        for details in courses.values():
            if not isinstance(details, dict):
                raise ValueError("Invalid course binding")  # noqa: TRY004
            try:
                identifier = uuid.UUID(str(details["class_course_id"]))
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                raise ValueError("Invalid course binding ID") from exc
            if identifier.int == 0:
                raise ValueError("Zero course binding ID is not allowed")
            identifiers.add(identifier)
        result[int(raw_user_id)] = frozenset(identifiers)
    return result


def current_principal(request: Request) -> PilotPrincipal:
    principal = getattr(request.state, "pilot_principal", None)
    if not isinstance(principal, PilotPrincipal):
        raise HTTPException(status_code=401, detail="Authentication required")
    return principal


def require_user_principal(request: Request) -> PilotPrincipal:
    principal = current_principal(request)
    if principal.role == "admin":
        return principal
    if principal.role != "pilot_user" or not principal.external_id:
        raise HTTPException(status_code=403, detail="User-scoped access required")
    return principal


def authorize_course(request: Request, class_course_id: uuid.UUID) -> PilotPrincipal:
    principal = require_user_principal(request)
    if principal.role == "admin":
        return principal
    settings = get_settings()
    try:
        bindings = parse_course_bindings(settings.telegram_course_bindings_json)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Course authorization is misconfigured") from exc
    allowed = bindings.get(int(principal.external_id or "0"), frozenset())
    if class_course_id not in allowed:
        raise HTTPException(status_code=403, detail="Course access denied")
    return principal


async def require_pilot_access(
    request: Request,
    x_pilot_key: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
    x_pilot_user_id: str | None = Header(default=None),
) -> PilotPrincipal:
    settings = get_settings()
    if (
        settings.admin_api_key
        and x_admin_key
        and secrets.compare_digest(x_admin_key, settings.admin_api_key)
    ):
        principal = PilotPrincipal("admin")
        request.state.pilot_principal = principal
        return principal
    if not is_strong_shared_key(settings.pilot_api_key):
        raise HTTPException(status_code=503, detail="Pilot API authentication is not configured")
    if not x_pilot_key or not secrets.compare_digest(x_pilot_key, settings.pilot_api_key):
        raise HTTPException(status_code=401, detail="Authentication required")

    if not x_pilot_user_id:
        raise HTTPException(status_code=403, detail="User-scoped access required")
    if not re.fullmatch(r"[1-9][0-9]*", x_pilot_user_id):
        raise HTTPException(status_code=401, detail="Invalid pilot principal")
    try:
        allowed_ids = parse_allowed_user_ids(settings.telegram_allowed_user_ids)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Pilot allowlist is misconfigured") from exc
    if int(x_pilot_user_id) not in allowed_ids:
        raise HTTPException(status_code=403, detail="Pilot user is not allowed")
    principal = PilotPrincipal("pilot_user", x_pilot_user_id)
    request.state.pilot_principal = principal
    return principal
