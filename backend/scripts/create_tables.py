"""Script to create notification tables."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import AsyncSessionLocal, engine
from app.models.base import BaseModel
from app.models.notification import Notification, NotificationConfig


async def create_tables():
    """Create notification tables."""
    async with engine.begin() as conn:
        # Create only notification tables
        await conn.run_sync(BaseModel.metadata.create_all, tables=[
            Notification.__table__,
            NotificationConfig.__table__,
        ])
    print("✅ Notification tables created successfully!")


if __name__ == "__main__":
    asyncio.run(create_tables())
