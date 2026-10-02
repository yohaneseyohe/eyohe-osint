from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from eyohe.api.deps import CSRF_COOKIE, DB, SESSION_COOKIE, Admin, CurrentUser, Principal, client_ip
from eyohe.core.config import get_settings
from eyohe.core.enums import Role
from eyohe.core.errors import ConflictError
from eyohe.schemas.auth import (
    ApiTokenCreated,
    ChangePasswordRequest,
    CreateUserRequest,
    LoginRequest,
    SessionOut,
    SetupRequest,
    SetupStatus,
    UserOut,
)
from eyohe.schemas.common import OkResponse
from eyohe.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookies(response: Response, raw_token: str, csrf: str, expires_at_seconds: int) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        raw_token,
        max_age=expires_at_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    # CSRF cookie is readable by the SPA which echoes it in the X-CSRF-Token header.
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=expires_at_seconds,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.get("/setup", response_model=SetupStatus)
async def setup_status(db: DB) -> SetupStatus:
    n = await auth_service.user_count(db)
    return SetupStatus(needs_setup=n == 0, user_count=n)


@router.post("/setup", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def setup_admin(payload: SetupRequest, request: Request, response: Response, db: DB) -> SessionOut:
    """First-run only: creates the admin account and signs in."""
    if await auth_service.user_count(db) > 0:
        raise ConflictError("Setup already completed. Sign in instead.")
    await auth_service.create_user(
        db,
        email=payload.email,
        username=payload.username,
        password=payload.password,
        display_name=payload.display_name,
        role=Role.ADMIN,
    )
    user, sess, raw = await auth_service.authenticate(
        db,
        identifier=payload.username,
        password=payload.password,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()
    _set_cookies(response, raw, sess.csrf_token, get_settings().session_ttl_hours * 3600)
    return SessionOut(user=UserOut.model_validate(user), csrf_token=sess.csrf_token, expires_at=sess.expires_at)


@router.post("/login", response_model=SessionOut)
async def login(payload: LoginRequest, request: Request, response: Response, db: DB) -> SessionOut:
    try:
        user, sess, raw = await auth_service.authenticate(
            db,
            identifier=payload.identifier,
            password=payload.password,
            ip=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except Exception:
        await db.commit()  # persist the LOGIN_FAILED audit row
        raise
    await db.commit()
    _set_cookies(response, raw, sess.csrf_token, get_settings().session_ttl_hours * 3600)
    return SessionOut(user=UserOut.model_validate(user), csrf_token=sess.csrf_token, expires_at=sess.expires_at)


@router.post("/logout", response_model=OkResponse)
async def logout(principal: Principal, response: Response, db: DB) -> OkResponse:
    user, sess = principal
    if sess is not None:
        await auth_service.logout(db, sess, user)
        await db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return OkResponse(message="Signed out.")


@router.get("/me", response_model=SessionOut)
async def me(principal: Principal) -> SessionOut:
    user, sess = principal
    from datetime import UTC, datetime, timedelta

    return SessionOut(
        user=UserOut.model_validate(user),
        csrf_token=sess.csrf_token if sess else "",
        expires_at=sess.expires_at if sess else datetime.now(UTC) + timedelta(days=365),
    )


@router.post("/password", response_model=OkResponse)
async def change_password(payload: ChangePasswordRequest, user: CurrentUser, db: DB) -> OkResponse:
    await auth_service.change_password(db, user, current=payload.current_password, new=payload.new_password)
    await db.commit()
    return OkResponse(message="Password changed. Other sessions were signed out.")


@router.get("/users", response_model=list[UserOut])
async def list_users(_: Admin, db: DB) -> list[UserOut]:
    return [UserOut.model_validate(u) for u in await auth_service.list_users(db)]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: CreateUserRequest, admin: Admin, db: DB) -> UserOut:
    user = await auth_service.create_user(
        db,
        email=payload.email,
        username=payload.username,
        password=payload.password,
        display_name=payload.display_name,
        role=Role(payload.role),
        actor=admin,
    )
    await db.commit()
    return UserOut.model_validate(user)


@router.post("/tokens", response_model=ApiTokenCreated, status_code=status.HTTP_201_CREATED)
async def create_token(user: CurrentUser, db: DB, name: str = "script") -> ApiTokenCreated:
    tok, raw = await auth_service.create_api_token(db, user, name)
    await db.commit()
    return ApiTokenCreated(
        id=tok.id, name=tok.name, created_at=tok.created_at, last_used_at=None, revoked=False, token=raw
    )
