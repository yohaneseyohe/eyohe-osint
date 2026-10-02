"""Users and sessions."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.core.config import get_settings
from eyohe.core.db import utcnow
from eyohe.core.enums import AuditAction, Role
from eyohe.core.errors import AuthenticationError, ConflictError, ValidationError
from eyohe.core.security import (
    hash_password,
    new_token,
    token_digest,
    validate_password_strength,
    verify_password,
)
from eyohe.models.auth import ApiToken, Session, User
from eyohe.services.audit import record_audit


async def user_count(session: AsyncSession) -> int:
    return int((await session.execute(select(func.count(User.id)))).scalar_one())


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    username: str,
    password: str,
    display_name: str = "",
    role: Role = Role.ANALYST,
    actor: User | None = None,
) -> User:
    email = email.strip().lower()
    username = username.strip().lower()
    if not username.isidentifier() and not username.replace("-", "_").replace(".", "_").isidentifier():
        raise ValidationError("Username may contain letters, digits, '.', '-' and '_' only.")
    if (err := validate_password_strength(password)) is not None:
        raise ValidationError(err)
    exists = await session.execute(select(User.id).where((User.email == email) | (User.username == username)))
    if exists.first():
        raise ConflictError("A user with that email or username already exists.")
    user = User(
        email=email,
        username=username,
        display_name=display_name or username,
        password_hash=hash_password(password),
        role=str(role),
    )
    session.add(user)
    await session.flush()
    await record_audit(
        session,
        AuditAction.USER_CREATED,
        actor_id=actor.id if actor else None,
        actor_label=actor.username if actor else "setup",
        object_type="user",
        object_id=str(user.id),
        detail={"username": username, "role": str(role)},
    )
    return user


async def authenticate(
    session: AsyncSession, *, identifier: str, password: str, ip: str | None, user_agent: str | None
) -> tuple[User, Session, str]:
    identifier = identifier.strip().lower()
    user = (
        await session.execute(select(User).where((User.email == identifier) | (User.username == identifier)))
    ).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        await record_audit(
            session,
            AuditAction.LOGIN_FAILED,
            actor_label=identifier[:64],
            ip_address=ip,
            detail={"reason": "invalid_credentials"},
        )
        raise AuthenticationError("Invalid username or password.")
    settings = get_settings()
    raw = new_token(32)
    now = utcnow()
    sess = Session(
        user_id=user.id,
        token_digest=token_digest(raw),
        csrf_token=new_token(24),
        created_at=now,
        expires_at=now + timedelta(hours=settings.session_ttl_hours),
        last_seen_at=now,
        ip_address=ip,
        user_agent=(user_agent or "")[:512],
    )
    user.last_login_at = now
    session.add(sess)
    await session.flush()
    await record_audit(
        session,
        AuditAction.USER_LOGIN,
        actor_id=user.id,
        actor_label=user.username,
        ip_address=ip,
        object_type="session",
        object_id=str(sess.id),
    )
    return user, sess, raw


async def resolve_session(session: AsyncSession, raw_token: str) -> tuple[User, Session] | None:
    digest = token_digest(raw_token)
    row = (
        await session.execute(
            select(Session, User).join(User, User.id == Session.user_id).where(Session.token_digest == digest)
        )
    ).first()
    if row is None:
        return None
    sess, user = row
    now = utcnow()
    if sess.revoked or sess.expires_at < now or not user.is_active:
        return None
    # Touch at most once a minute to avoid write amplification.
    if (now - sess.last_seen_at).total_seconds() > 60:
        await session.execute(update(Session).where(Session.id == sess.id).values(last_seen_at=now))
        await session.commit()
    return user, sess


async def resolve_api_token(session: AsyncSession, raw_token: str) -> User | None:
    digest = token_digest(raw_token)
    row = (
        await session.execute(
            select(ApiToken, User).join(User, User.id == ApiToken.user_id).where(ApiToken.token_digest == digest)
        )
    ).first()
    if row is None:
        return None
    tok, user = row
    if tok.revoked or not user.is_active:
        return None
    tok.last_used_at = utcnow()
    await session.commit()
    return user


async def logout(session: AsyncSession, sess: Session, user: User) -> None:
    sess.revoked = True
    await record_audit(session, AuditAction.USER_LOGOUT, actor_id=user.id, actor_label=user.username)


async def change_password(session: AsyncSession, user: User, *, current: str, new: str) -> None:
    if not verify_password(current, user.password_hash):
        raise AuthenticationError("Current password is incorrect.")
    if (err := validate_password_strength(new)) is not None:
        raise ValidationError(err)
    user.password_hash = hash_password(new)
    # Revoke other sessions on password change.
    await session.execute(update(Session).where(Session.user_id == user.id).values(revoked=True))


async def create_api_token(session: AsyncSession, user: User, name: str) -> tuple[ApiToken, str]:
    raw = "eyo_" + new_token(32)
    tok = ApiToken(user_id=user.id, name=name[:128], token_digest=token_digest(raw))
    session.add(tok)
    await session.flush()
    return tok, raw


async def list_users(session: AsyncSession) -> list[User]:
    return list((await session.execute(select(User).order_by(User.created_at))).scalars())


def get_user_by_id_stmt(user_id: uuid.UUID):  # type: ignore[no-untyped-def]
    return select(User).where(User.id == user_id)
