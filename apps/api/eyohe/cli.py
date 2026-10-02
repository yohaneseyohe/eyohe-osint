"""Eyohe CLI: `python -m eyohe.cli <command>`.

Commands:
  seed            create the admin user interactively (or from env EYOHE_ADMIN_*) and optional demo case
  create-user     create a user
  health          print health JSON
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import sys

from eyohe.core.db import get_session_factory
from eyohe.core.enums import Role
from eyohe.core.logging import configure_logging


async def _seed(demo: bool) -> None:
    from eyohe.services import auth as auth_service

    async with get_session_factory()() as db:
        if await auth_service.user_count(db) == 0:
            email = os.environ.get("EYOHE_ADMIN_EMAIL") or input("Admin email: ").strip()  # noqa: ASYNC250
            username = os.environ.get("EYOHE_ADMIN_USERNAME") or input("Admin username: ").strip()  # noqa: ASYNC250
            password = os.environ.get("EYOHE_ADMIN_PASSWORD") or getpass.getpass("Admin password (min 10 chars): ")
            await auth_service.create_user(
                db, email=email, username=username, password=password, role=Role.ADMIN, display_name=username
            )
            await db.commit()
            print(f"Created admin user '{username}'.")
        else:
            print("Users already exist; skipping admin creation.")
        if demo:
            from eyohe.services.demo import create_demo_case

            case = await create_demo_case(db)
            await db.commit()
            print(f"Created demo case {case.display_id} (clearly labelled DEMO DATA).")


async def _create_user(email: str, username: str, role: str) -> None:
    from eyohe.services import auth as auth_service

    password = getpass.getpass("Password (min 10 chars): ")
    async with get_session_factory()() as db:
        await auth_service.create_user(db, email=email, username=username, password=password, role=Role(role))
        await db.commit()
    print(f"Created user '{username}' with role {role}.")


async def _health() -> None:
    from eyohe.services.health import full_health

    async with get_session_factory()() as db:
        print(json.dumps(await full_health(db), indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    p = argparse.ArgumentParser(prog="eyohe")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seed")
    s.add_argument("--demo", action="store_true", help="also create the fictional demo case")
    c = sub.add_parser("create-user")
    c.add_argument("email")
    c.add_argument("username")
    c.add_argument("--role", default="analyst", choices=["admin", "analyst", "viewer"])
    sub.add_parser("health")
    args = p.parse_args(argv)
    if args.cmd == "seed":
        asyncio.run(_seed(args.demo))
    elif args.cmd == "create-user":
        asyncio.run(_create_user(args.email, args.username, args.role))
    elif args.cmd == "health":
        asyncio.run(_health())
    return 0


if __name__ == "__main__":
    sys.exit(main())
