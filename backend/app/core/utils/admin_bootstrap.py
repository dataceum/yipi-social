import asyncio
import os
import sys
from datetime import date

sys.path.append(os.getcwd())

from sqlmodel import select, SQLModel
from app.core.db import engine, async_session_maker
from app.core.security import hash_password
from app.models.enums import Gender, UserRole
from app.models.user import User


async def main():
    print("🚀 Initializing CRM Administrative Bootstrap System...")

    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with async_session_maker() as db:
        stmt = select(User).where(User.role == UserRole.ADMIN)
        existing_admin = (await db.exec(stmt)).one_or_none()

        if existing_admin:
            print("⚠️ Bootstrap Aborted: Admin account already exists.")
            return

        print("👤 Compiling administrator account details...")
        admin_user = User(
            username="admin",
            first_name="System",
            last_name="Administrator",
            email="admin@yourdomain.com",
            birth_date=date(1970, 1, 1),
            phone_number="+10000000000",
            hashed_password=await hash_password("D@taC3um1957"),
            role=UserRole.ADMIN,
            gender=Gender.MALE,
            is_active=True,
        )
        db.add(admin_user)
        await db.commit()

        print("✅ Success: Admin account created successfully!")


if __name__ == "__main__":
    asyncio.run(main())
