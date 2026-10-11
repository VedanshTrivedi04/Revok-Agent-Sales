import sys
sys.path.insert(0, r"D:\CDGI2026\revops-agent\apps\api")
import asyncio
from uuid import UUID, uuid4
from app.db.session import admin_session, get_engine
from app.models import tenancy
from app.auth.passwords import hash_password
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

PRAGYAN_ORG = UUID("01a12aaf-5ea3-7153-91c3-9866a22d91b4")
PASSWORD = "Demo@12345678"

ROLES_TO_CREATE = [
    {"email": "admin@pragyan.example.com", "name": "Pragyan Admin", "role": "admin"},
    {"email": "manager@pragyan.example.com", "name": "Pragyan Manager", "role": "manager"},
    {"email": "csm@pragyan.example.com", "name": "Pragyan CSM Member", "role": "member"},
    {"email": "viewer@pragyan.example.com", "name": "Pragyan Viewer", "role": "viewer"},
]

async def main():
    pw_hash = hash_password(PASSWORD)
    async with admin_session() as s:
        for item in ROLES_TO_CREATE:
            email = item["email"]
            name = item["name"]
            role = item["role"]

            # 1. User
            user = (await s.execute(select(tenancy.User).where(tenancy.User.email == email))).scalar_one_or_none()
            if not user:
                user_id = uuid4()
                await s.execute(insert(tenancy.User).values({
                    "id": user_id,
                    "email": email,
                    "name": name,
                    "password_hash": pw_hash,
                    "is_superadmin": False,
                    "failed_login_count": 0,
                    "locked_until": None,
                }))
            else:
                user_id = user.id
                user.password_hash = pw_hash
                user.failed_login_count = 0
                user.locked_until = None
            await s.flush()

            # 2. Membership
            membership = (await s.execute(
                select(tenancy.Membership).where(
                    tenancy.Membership.org_id == PRAGYAN_ORG,
                    tenancy.Membership.user_id == user_id
                )
            )).scalar_one_or_none()
            if not membership:
                await s.execute(insert(tenancy.Membership).values({
                    "id": uuid4(),
                    "org_id": PRAGYAN_ORG,
                    "user_id": user_id,
                    "role": role,
                    "status": "active"
                }))
            else:
                membership.role = role
                membership.status = "active"
            await s.flush()
            print(f"Created/Updated {role}: {email}")

    await get_engine().dispose()
    print("ALL PRAGYAN ROLES READY!")

if __name__ == "__main__":
    asyncio.run(main())
