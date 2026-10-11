"""Create or reset a user's sign-in password (and optionally mark them platform superadmin).

Usage: uv run python scripts/set_password.py <email> [--name "Full Name"] [--superadmin]
The password is read from a hidden prompt (or the REVOPS_PASSWORD env var), never from argv.
Runs against whatever DATABASE_* URLs are configured, so check your .env first.
"""

import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.auth.passwords import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, hash_password  # noqa: E402
from app.db.session import admin_session, get_admin_engine  # noqa: E402
from app.models.tenancy import User  # noqa: E402
from app.utils.ids import new_id  # noqa: E402


async def run(email: str, name: str | None, superadmin: bool, password: str) -> None:
    async with admin_session() as s:
        user = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
        created = user is None
        if user is None:
            user = User(id=new_id(), email=email.strip().lower(), name=name)
            s.add(user)
        elif name:
            user.name = name
        user.password_hash = hash_password(password)
        user.failed_login_count = 0
        user.locked_until = None
        if superadmin:
            user.is_superadmin = True
    await get_admin_engine().dispose()
    print(
        f"{'created' if created else 'updated'} {email}" + (" (superadmin)" if superadmin else "")
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("email")
    ap.add_argument("--name")
    ap.add_argument("--superadmin", action="store_true", help="also set users.is_superadmin")
    args = ap.parse_args()
    password = os.environ.get("REVOPS_PASSWORD") or getpass.getpass("New password: ")
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise SystemExit(f"password must be {MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} characters")
    asyncio.run(run(args.email, args.name, args.superadmin, password))


if __name__ == "__main__":
    main()
