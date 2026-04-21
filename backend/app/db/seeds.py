"""Development database seeds."""

import asyncio

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.database import AsyncSessionLocal
from app.models.organization import Organization
from app.models.user import User, UserRole


async def seed_database() -> None:
    """Seed database with development data."""
    async with AsyncSessionLocal() as session:
        # Check if data already exists
        result = await session.execute(select(Organization))
        if result.scalars().first():
            print("Database already seeded, skipping...")
            return

        # Create default organization
        org = Organization(
            name="Acme Corporation",
            slug="acme-corp",
            description="Default organization for development",
        )
        session.add(org)
        await session.flush()

        # Create admin user
        admin = User(
            email="admin@example.com",
            hashed_password=get_password_hash("admin123"),
            full_name="Admin User",
            role=UserRole.ADMIN,
            is_active=True,
            organization_id=org.id,
        )
        session.add(admin)

        # Create editor user
        editor = User(
            email="editor@example.com",
            hashed_password=get_password_hash("editor123"),
            full_name="Editor User",
            role=UserRole.EDITOR,
            is_active=True,
            organization_id=org.id,
        )
        session.add(editor)

        # Create viewer user
        viewer = User(
            email="viewer@example.com",
            hashed_password=get_password_hash("viewer123"),
            full_name="Viewer User",
            role=UserRole.VIEWER,
            is_active=True,
            organization_id=org.id,
        )
        session.add(viewer)

        await session.commit()
        print("Database seeded successfully!")
        print("\nDevelopment accounts:")
        print("  admin@example.com / admin123 (ADMIN)")
        print("  editor@example.com / editor123 (EDITOR)")
        print("  viewer@example.com / viewer123 (VIEWER)")


if __name__ == "__main__":
    asyncio.run(seed_database())
