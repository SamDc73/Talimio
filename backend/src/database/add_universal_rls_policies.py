"""
Add Row Level Security policies that handle ALL auth logic
Run this ONCE and never think about user_id checks again!
"""
import asyncio

from sqlalchemy.ext.asyncio import AsyncEngine

from src.database.session import engine


async def add_universal_rls_policies(engine: AsyncEngine):
    """
    Create RLS policies that work for BOTH single-user and multi-user modes
    
    The magic: In single-user mode, auth.uid() returns NULL, so we use COALESCE
    to fallback to our DEFAULT_USER_ID. In multi-user mode, it returns the actual user.
    """
    # Tables that need RLS (based on actual database tables with user_id column)
    tables_with_user_id = [
        "books", "videos", "roadmaps", "flashcard_decks",
        "progress", "book_progress", "video_progress", "user_progress",
        "user_custom_instructions", "tag_associations"
    ]

    async with engine.connect() as conn:
        await conn.exec_driver_sql("BEGIN")

        try:
            # Enable RLS on all tables
            for table in tables_with_user_id:
                await conn.exec_driver_sql(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

            # Create a universal policy for each table
            for table in tables_with_user_id:
                # Drop existing policies
                await conn.exec_driver_sql(f"""
                    DROP POLICY IF EXISTS "{table}_user_policy" ON {table}
                """)

                # Create new policy that handles BOTH modes
                await conn.exec_driver_sql(f"""
                    CREATE POLICY "{table}_user_policy" ON {table}
                    FOR ALL
                    TO authenticated, anon
                    USING (
                        user_id = COALESCE(
                            (SELECT auth.uid()),  -- Multi-user: returns actual user ID
                            '00000000-0000-0000-0000-000000000001'::uuid  -- Single-user: fallback
                        )
                    )
                    WITH CHECK (
                        user_id = COALESCE(
                            (SELECT auth.uid()),
                            '00000000-0000-0000-0000-000000000001'::uuid
                        )
                    )
                """)

                print(f"✅ Added RLS policy for {table}")

            # Special handling for user_preferences table (it has user_id, not id)
            await conn.exec_driver_sql("""
                ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY
            """)

            await conn.exec_driver_sql("""
                DROP POLICY IF EXISTS "user_preferences_policy" ON user_preferences
            """)

            await conn.exec_driver_sql("""
                CREATE POLICY "user_preferences_policy" ON user_preferences
                FOR ALL
                TO authenticated, anon
                USING (
                    user_id = COALESCE(
                        (SELECT auth.uid()),
                        '00000000-0000-0000-0000-000000000001'::uuid
                    )
                )
                WITH CHECK (
                    user_id = COALESCE(
                        (SELECT auth.uid()),
                        '00000000-0000-0000-0000-000000000001'::uuid
                    )
                )
            """)

            await conn.exec_driver_sql("COMMIT")
            print("✅ ALL RLS policies created successfully!")

        except Exception as e:
            await conn.exec_driver_sql("ROLLBACK")
            print(f"❌ Error creating RLS policies: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(add_universal_rls_policies(engine))
