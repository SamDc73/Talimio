"""Test tagging functionality in both single-user and multi-user modes.

Testing Strategy:
1. Database: Use a real test database (PostgreSQL with pgvector)
2. AI Services: Mock via conftest.py service boundary mocking
3. Authentication: Use real JWT validation with Supabase secret
4. External APIs: ALL mocked to prevent hanging and cost

This test suite validates tagging works correctly across all content types.
"""

import importlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import src.tagging.service as tagging_service_module
from src.tagging.schemas import TagWithConfidence
from tests.fixtures.auth_modes import AuthMode


TaggingService = tagging_service_module.TaggingService
TaggedContent = tagging_service_module.TaggedContent


@pytest.fixture(autouse=True)
def restore_tagging_service(mock_external_services):
    """Reload TaggingService so tests use the real implementation."""
    module = importlib.reload(tagging_service_module)
    globals()["TaggingService"] = module.TaggingService
    globals()["TaggedContent"] = module.TaggedContent
    return module


@pytest.fixture(autouse=True)
async def mock_tagging_llm_client(restore_tagging_service):
    """Mock LiteLLM client used by TaggingService."""
    with patch("src.tagging.service.LLMClient") as mock_llm_cls:
        mock_instance = MagicMock()
        mock_response = TaggedContent(
            tags=[
                TagWithConfidence(tag="python", confidence=0.95),
                TagWithConfidence(tag="programming", confidence=0.85),
                TagWithConfidence(tag="backend", confidence=0.75),
            ]
        )

        async def mock_get_completion(*_args, **_kwargs):
            return mock_response

        mock_instance.get_completion = AsyncMock(side_effect=mock_get_completion)
        mock_llm_cls.return_value = mock_instance
        yield mock_llm_cls


@pytest.fixture(autouse=True)
async def mock_litellm_env():
    """Mock TAGGING_LLM_MODEL environment variable."""
    with patch.dict("os.environ", {"TAGGING_LLM_MODEL": "gpt-4"}):
        yield


@pytest.mark.dual_mode
@pytest.mark.parametrize("auth_mode", [AuthMode.SINGLE_USER, AuthMode.MULTI_USER], indirect=True)
class TestTaggingIntegration:
    """Test tagging functionality across content types in both auth modes."""

    @pytest.mark.asyncio
    async def test_tagging_endpoints_accessible(self, client_factory, auth_mode) -> None:
        """Test that tagging endpoints are accessible in both auth modes."""
        # Create client based on auth mode
        if auth_mode == AuthMode.SINGLE_USER:
            client = await client_factory()
        else:  # MULTI_USER
            client = await client_factory("test-user@example.com")

        # Test tag listing endpoint
        response = await client.get("/api/v1/tags")
        assert response.status_code != 500, f"Tags list got 500 error: {response.text}"

        # Expected successful codes
        expected_codes = [200, 404]  # 200 for success, 404 if no tags
        assert response.status_code in expected_codes

    @pytest.mark.asyncio
    async def test_course_tagging_via_llm(
        self,
        client_factory,
        auth_mode,
        db_session: AsyncSession,
    ) -> None:
        """Test that courses can be tagged via LiteLLM structured output."""
        # Create client based on auth mode
        if auth_mode == AuthMode.SINGLE_USER:
            client = await client_factory()
            user_id = uuid.UUID("00000000-0000-0000-0000-000000000000")  # Default single-user ID
        else:  # MULTI_USER
            client = await client_factory("test-user@example.com")
            user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")  # Test user ID

        # Test tagging service directly
        tagging_service = TaggingService(db_session)
        content_id = uuid.uuid4()

        # Tag the content
        tags = await tagging_service.tag_content(
            content_id=content_id,
            content_type="course",
            user_id=user_id,
            title="Advanced Python Programming",
            content_preview="Learn async programming, decorators, and metaclasses",
        )

        # Verify tags were generated
        assert len(tags) == 3
        assert "python" in tags
        assert "programming" in tags
        assert "backend" in tags

        # Verify tags were stored in database
        stored_tags = await tagging_service.get_content_tags(
            content_id=content_id,
            content_type="course",
            user_id=user_id,
        )

        assert len(stored_tags) == 3
        tag_names = [tag.name for tag in stored_tags]
        assert "python" in tag_names
        assert "programming" in tag_names
        assert "backend" in tag_names

    @pytest.mark.asyncio
    async def test_video_tagging_via_llm(
        self,
        client_factory,
        auth_mode,
        db_session: AsyncSession,
    ) -> None:
        """Test that videos can be tagged via LiteLLM structured output."""
        # Create client based on auth mode
        if auth_mode == AuthMode.SINGLE_USER:
            client = await client_factory()
            user_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        else:  # MULTI_USER
            client = await client_factory("test-user@example.com")
            user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        # Test tagging service directly
        tagging_service = TaggingService(db_session)
        content_id = uuid.uuid4()

        # Tag the video
        tags = await tagging_service.tag_content(
            content_id=content_id,
            content_type="video",
            user_id=user_id,
            title="Machine Learning Fundamentals",
            content_preview="Introduction to neural networks and deep learning",
        )

        # Verify tags were generated
        assert len(tags) == 3
        assert "python" in tags  # Our mock always returns these
        assert "programming" in tags
        assert "backend" in tags

        # Verify tags were stored
        stored_tags = await tagging_service.get_content_tags(
            content_id=content_id,
            content_type="video",
            user_id=user_id,
        )

        assert len(stored_tags) == 3

    @pytest.mark.asyncio
    async def test_book_tagging_via_llm(
        self,
        client_factory,
        auth_mode,
        db_session: AsyncSession,
    ) -> None:
        """Test that books can be tagged via LiteLLM structured output."""
        # Create client based on auth mode
        if auth_mode == AuthMode.SINGLE_USER:
            client = await client_factory()
            user_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        else:  # MULTI_USER
            client = await client_factory("test-user@example.com")
            user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        # Test tagging service directly
        tagging_service = TaggingService(db_session)
        content_id = uuid.uuid4()

        # Tag the book
        tags = await tagging_service.tag_content(
            content_id=content_id,
            content_type="book",
            user_id=user_id,
            title="Clean Code: A Handbook of Agile Software Craftsmanship",
            content_preview="Best practices for writing maintainable code",
        )

        # Verify tags were generated
        assert len(tags) == 3
        assert "python" in tags
        assert "programming" in tags
        assert "backend" in tags

        # Verify tags were stored
        stored_tags = await tagging_service.get_content_tags(
            content_id=content_id,
            content_type="book",
            user_id=user_id,
        )

        assert len(stored_tags) == 3

    @pytest.mark.asyncio
    async def test_tag_suggestions_via_llm(
        self,
        client_factory,
        auth_mode,
        db_session: AsyncSession,
    ) -> None:
        """Test that tag suggestions work with the LiteLLM structured path."""
        # Create client based on auth mode
        if auth_mode == AuthMode.SINGLE_USER:
            client = await client_factory()
            user_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        else:  # MULTI_USER
            client = await client_factory("test-user@example.com")
            user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        # Test tag suggestions
        tagging_service = TaggingService(db_session)

        suggestions = await tagging_service.suggest_tags(
            content_preview="Deep learning with TensorFlow and Keras",
            _user_id=user_id,
            _content_type="course",
            title="Deep Learning Masterclass",
        )

        # Verify suggestions were generated
        assert len(suggestions) == 3
        assert "python" in suggestions
        assert "programming" in suggestions
        assert "backend" in suggestions

    @pytest.mark.asyncio
    async def test_batch_tagging_via_llm(
        self,
        client_factory,
        auth_mode,
        db_session: AsyncSession,
    ) -> None:
        """Test batch tagging multiple content items via LiteLLM."""
        # Create client based on auth mode
        if auth_mode == AuthMode.SINGLE_USER:
            client = await client_factory()
            user_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        else:  # MULTI_USER
            client = await client_factory("test-user@example.com")
            user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        # Test batch tagging
        tagging_service = TaggingService(db_session)

        content_items = [
            {
                "content_id": str(uuid.uuid4()),
                "content_type": "course",
                "user_id": str(user_id),
                "title": "Python Advanced",
                "preview": "Advanced Python concepts",
            },
            {
                "content_id": str(uuid.uuid4()),
                "content_type": "video",
                "user_id": str(user_id),
                "title": "JavaScript Basics",
                "preview": "Learn JavaScript fundamentals",
            },
            {
                "content_id": str(uuid.uuid4()),
                "content_type": "book",
                "user_id": str(user_id),
                "title": "Design Patterns",
                "preview": "Software design patterns",
            },
        ]

        result = await tagging_service.batch_tag_content(content_items)

        # Verify batch results
        assert result["total"] == 3
        assert result["successful"] == 3
        assert result["failed"] == 0

        # Each item should have tags
        for item_result in result["results"]:
            assert item_result["success"] is True
            assert len(item_result["tags"]) == 3

    @pytest.mark.asyncio
    async def test_manual_tag_update(
        self,
        client_factory,
        auth_mode,
        db_session: AsyncSession,
    ) -> None:
        """Test manual tag updates replace auto-generated tags."""
        # Create client based on auth mode
        if auth_mode == AuthMode.SINGLE_USER:
            client = await client_factory()
            user_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        else:  # MULTI_USER
            client = await client_factory("test-user@example.com")
            user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

        tagging_service = TaggingService(db_session)
        content_id = uuid.uuid4()

        # First, auto-generate tags
        auto_tags = await tagging_service.tag_content(
            content_id=content_id,
            content_type="course",
            user_id=user_id,
            title="Test Course",
            content_preview="Test content",
        )

        assert len(auto_tags) == 3

        # Now update with manual tags
        manual_tags = ["react", "frontend", "javascript"]
        await tagging_service.update_manual_tags(
            content_id=content_id,
            content_type="course",
            user_id=user_id,
            tag_names=manual_tags,
        )

        # Verify manual tags replaced auto-generated ones
        stored_tags = await tagging_service.get_content_tags(
            content_id=content_id,
            content_type="course",
            user_id=user_id,
        )

        tag_names = [tag.name for tag in stored_tags]
        assert len(tag_names) == 3
        assert "react" in tag_names
        assert "frontend" in tag_names
        assert "javascript" in tag_names
        # Auto-generated tags should be gone
        assert "python" not in tag_names
        assert "programming" not in tag_names
        assert "backend" not in tag_names

    @pytest.mark.asyncio
    async def test_llm_failure_returns_empty_tags(
        self,
        client_factory,
        auth_mode,
        db_session: AsyncSession,
    ) -> None:
        """Ensure TaggingService handles LiteLLM failures gracefully."""
        with patch("src.tagging.service.LLMClient") as mock_llm_cls:
            mock_instance = MagicMock()
            mock_instance.get_completion = AsyncMock(side_effect=RuntimeError("Validation failed"))
            mock_llm_cls.return_value = mock_instance

            if auth_mode == AuthMode.SINGLE_USER:
                client = await client_factory()
                user_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
            else:  # MULTI_USER
                client = await client_factory("test-user@example.com")
                user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")

            tagging_service = TaggingService(db_session)
            content_id = uuid.uuid4()

            tags = await tagging_service.tag_content(
                content_id=content_id,
                content_type="course",
                user_id=user_id,
                title="Test Course",
                content_preview="Test content",
            )

            assert tags == []

    @pytest.mark.asyncio
    async def test_tagging_auth_isolation(
        self,
        client_factory,
        auth_mode,
        db_session: AsyncSession,
    ) -> None:
        """Test that tagging respects auth mode isolation."""
        tagging_service = TaggingService(db_session)
        content_id = uuid.uuid4()

        if auth_mode == AuthMode.SINGLE_USER:
            # Single-user mode: all requests share same context
            client1 = await client_factory()
            client2 = await client_factory()
            user_id = uuid.UUID("00000000-0000-0000-0000-000000000000")

            # Tag content with first client
            tags1 = await tagging_service.tag_content(
                content_id=content_id,
                content_type="course",
                user_id=user_id,
                title="Shared Course",
                content_preview="Course content",
            )

            # Get tags with second client - should see same tags
            tags2 = await tagging_service.get_content_tags(
                content_id=content_id,
                content_type="course",
                user_id=user_id,
            )

            assert len(tags1) == len(tags2)

        else:  # MULTI_USER
            # Multi-user mode: different users are isolated
            client1 = await client_factory("user1@test.com")
            client2 = await client_factory("user2@test.com")
            user1_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
            user2_id = uuid.UUID("22222222-2222-2222-2222-222222222222")

            # User 1 tags content
            tags1 = await tagging_service.tag_content(
                content_id=content_id,
                content_type="course",
                user_id=user1_id,
                title="User1 Course",
                content_preview="Course content",
            )

            # User 2 shouldn't see User 1's tags
            tags2 = await tagging_service.get_content_tags(
                content_id=content_id,
                content_type="course",
                user_id=user2_id,
            )

            assert len(tags1) == 3
            assert len(tags2) == 0  # User 2 has no tags for this content


@pytest.mark.dual_mode
@pytest.mark.parametrize("auth_mode", [AuthMode.MULTI_USER], indirect=True)
class TestTagDataIsolation:
    """Test that tags are properly isolated between users in multi-user mode."""

    @pytest.mark.asyncio
    async def test_tags_isolated_between_users(
        self,
        client_factory,
        auth_mode,
        db_session: AsyncSession,
    ) -> None:
        """Test that users can only see and modify their own tags."""
        # Create two different users
        client1 = await client_factory("user1@test.com")
        client2 = await client_factory("user2@test.com")
        user1_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        user2_id = uuid.UUID("22222222-2222-2222-2222-222222222222")

        tagging_service = TaggingService(db_session)
        content_id = uuid.uuid4()

        # User 1 creates tags
        user1_tags = await tagging_service.tag_content(
            content_id=content_id,
            content_type="course",
            user_id=user1_id,
            title="Shared Content",
            content_preview="Content that both users access",
        )

        # User 2 creates different tags for same content
        user2_tags = await tagging_service.tag_content(
            content_id=content_id,
            content_type="course",
            user_id=user2_id,
            title="Shared Content",
            content_preview="Content that both users access",
        )

        # Verify each user sees only their own tags
        user1_stored = await tagging_service.get_content_tags(
            content_id=content_id,
            content_type="course",
            user_id=user1_id,
        )

        user2_stored = await tagging_service.get_content_tags(
            content_id=content_id,
            content_type="course",
            user_id=user2_id,
        )

        # Both should have tags
        assert len(user1_stored) == 3
        assert len(user2_stored) == 3

        # Tags are the same because our mock returns the same tags
        # But they should be stored separately per user
        user1_tag_names = {tag.name for tag in user1_stored}
        user2_tag_names = {tag.name for tag in user2_stored}

        # In a real scenario, these could be different
        # But our mock returns the same tags
        assert user1_tag_names == user2_tag_names

        # Verify User 1 can update their tags without affecting User 2
        await tagging_service.update_manual_tags(
            content_id=content_id,
            content_type="course",
            user_id=user1_id,
            tag_names=["updated", "tags", "user1"],
        )

        # User 1's tags should be updated
        user1_updated = await tagging_service.get_content_tags(
            content_id=content_id,
            content_type="course",
            user_id=user1_id,
        )

        # User 2's tags should remain unchanged
        user2_unchanged = await tagging_service.get_content_tags(
            content_id=content_id,
            content_type="course",
            user_id=user2_id,
        )

        user1_updated_names = {tag.name for tag in user1_updated}
        user2_unchanged_names = {tag.name for tag in user2_unchanged}

        assert "updated" in user1_updated_names
        assert "updated" not in user2_unchanged_names
        assert user2_unchanged_names == {"python", "programming", "backend"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
