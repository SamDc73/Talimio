"""Fix CASCADE DELETE on nodes.parent_id foreign key.

This migration updates the foreign key constraint on nodes.parent_id to include
CASCADE DELETE, allowing parent nodes to be deleted when they have children.
"""

import logging
import sys
from pathlib import Path

# Add the backend directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from sqlalchemy import text
from src.database.session import async_session_maker

logger = logging.getLogger(__name__)


async def upgrade() -> None:
    """Update the nodes.parent_id foreign key to add CASCADE DELETE."""
    async with async_session_maker() as session:
        try:
            # Drop the existing foreign key constraint
            await session.execute(text("""
                ALTER TABLE nodes 
                DROP CONSTRAINT IF EXISTS nodes_parent_id_fkey
            """))
            
            # Add the foreign key constraint with CASCADE DELETE
            await session.execute(text("""
                ALTER TABLE nodes 
                ADD CONSTRAINT nodes_parent_id_fkey 
                FOREIGN KEY (parent_id) 
                REFERENCES nodes(id) 
                ON DELETE CASCADE
            """))
            
            await session.commit()
            logger.info("✅ Successfully updated nodes.parent_id foreign key with CASCADE DELETE")
            print("✅ Successfully updated nodes.parent_id foreign key with CASCADE DELETE")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Migration failed: {e}")
            print(f"❌ Migration failed: {e}")
            raise


async def downgrade() -> None:
    """Restore the original foreign key constraint without CASCADE DELETE."""
    async with async_session_maker() as session:
        try:
            # Drop the CASCADE foreign key constraint
            await session.execute(text("""
                ALTER TABLE nodes 
                DROP CONSTRAINT IF EXISTS nodes_parent_id_fkey
            """))
            
            # Add back the foreign key constraint without CASCADE DELETE
            await session.execute(text("""
                ALTER TABLE nodes 
                ADD CONSTRAINT nodes_parent_id_fkey 
                FOREIGN KEY (parent_id) 
                REFERENCES nodes(id)
            """))
            
            await session.commit()
            logger.info("✅ Restored original nodes.parent_id foreign key without CASCADE DELETE")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Downgrade failed: {e}")
            raise


if __name__ == "__main__":
    import asyncio
    asyncio.run(upgrade())