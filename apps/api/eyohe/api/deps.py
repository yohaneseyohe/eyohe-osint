"""FastAPI dependencies: database session, current user, role checks, CSRF."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.core.db import get_db
from eyohe.core.enums import Role
from eyohe.core.errors import AuthenticationError, PermissionDeniedError
from eyohe.core.security import constant_time_equals
from eyohe.models.auth import Session, User
from eyohe.services import auth as auth_service

SESSION_COOKIE = "eyohe_session"
CSRF_COOKIE = "eyohe_csrf"
CSRF_HEADER = "x-csrf-token"

DB = Annotated[AsyncSession, Depends(get_db)]


async def get_current_principal(request: Request, db: DB) -> tuple[User, Session | None]:
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        user = await auth_service.resolve_api_token(db, auth_header[7:].strip())
        if user is None:
            raise AuthenticationError("Invalid API token.")
        return user, None
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        raise AuthenticationError("Not signed in.")
    resolved = await auth_service.resolve_session(db, raw)
    if resolved is None:
        raise AuthenticationError("Session expired or invalid. Please sign in again.")
    user, sess = resolved
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        header = request.headers.get(CSRF_HEADER, "")
        if not header or not constant_time_equals(header, sess.csrf_token):
            raise PermissionDeniedError("CSRF token missing or invalid.")
    return user, sess


async def get_current_user(principal: Annotated[tuple[User, Session | None], Depends(get_current_principal)]) -> User:
    return principal[0]


CurrentUser = Annotated[User, Depends(get_current_user)]
Principal = Annotated[tuple[User, Session | None], Depends(get_current_principal)]

_ROLE_RANK = {Role.VIEWER: 0, Role.ANALYST: 1, Role.ADMIN: 2}


def require_role(minimum: Role) -> Callable[[User], User]:
    async def _check(user: CurrentUser) -> User:
        if _ROLE_RANK.get(Role(user.role), -1) < _ROLE_RANK[minimum]:
            raise PermissionDeniedError(f"This action requires the '{minimum}' role.")
        return user

    return _check  # type: ignore[return-value]


Analyst = Annotated[User, Depends(require_role(Role.ANALYST))]
Admin = Annotated[User, Depends(require_role(Role.ADMIN))]


def client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None
