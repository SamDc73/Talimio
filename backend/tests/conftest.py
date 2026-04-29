from __future__ import annotations

import asyncio
import importlib
import os
import re
import shutil
import sys
import tempfile
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self, cast

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.ai.litellm_config import cleanup_litellm_async_clients
from src.auth.config import DEFAULT_USER_ID
from src.auth.crud import create_auth_session
from src.auth.security import create_access_token
from src.config.settings import get_settings
from src.database.migrate import apply_migrations
from src.user.models import User
from tests.fixtures.auth_modes import AuthMode


_SETTINGS = get_settings()
_TEST_SCHEMA_NAME = f"pytest_{uuid.uuid4().hex}"
_TEST_STORAGE_PATH = Path(tempfile.mkdtemp(prefix="talimio-backend-tests-"))
_DEFAULT_MULTI_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
_FIXED_EMAIL_USER_IDS = {
    "test-user@example.com": _DEFAULT_MULTI_USER_ID,
    "user1@test.com": _DEFAULT_MULTI_USER_ID,
    "user2@test.com": uuid.UUID("22222222-2222-2222-2222-222222222222"),
}


def _reload_settings() -> Any:
    global _SETTINGS  # noqa: PLW0603
    get_settings.cache_clear()
    _SETTINGS = get_settings()
    return _SETTINGS


def _configure_test_settings() -> None:
    os.environ["ENVIRONMENT"] = "test"
    os.environ["AUTH_PROVIDER"] = "none"
    os.environ["MIGRATIONS_VERBOSE"] = "false"
    os.environ["OTEL_ENABLED"] = "false"
    os.environ["LOCAL_STORAGE_PATH"] = str(_TEST_STORAGE_PATH)
    os.environ["FRONTEND_URL"] = "http://testserver"
    os.environ["FRONTEND_APP_URL"] = "http://testserver"

    if not os.environ.get("AUTH_SECRET_KEY", "").strip():
        os.environ["AUTH_SECRET_KEY"] = "test-auth-secret"  # noqa: S105

    if not os.environ.get("PRIMARY_LLM_MODELS", "").strip():
        os.environ["PRIMARY_LLM_MODELS"] = "gpt-4o-mini"

    if not os.environ.get("FAST_LLM_MODEL", "").strip():
        os.environ["FAST_LLM_MODEL"] = "gpt-4o-mini"

    if not os.environ.get("RAG_EMBEDDING_OUTPUT_DIM", "").strip():
        os.environ["RAG_EMBEDDING_OUTPUT_DIM"] = "3"

    if not os.environ.get("MEMORY_EMBEDDING_OUTPUT_DIM", "").strip():
        os.environ["MEMORY_EMBEDDING_OUTPUT_DIM"] = "3"

    settings = _reload_settings()
    if not settings.AUTH_SECRET_KEY.get_secret_value().strip():
        settings.AUTH_SECRET_KEY = SecretStr("test-auth-secret")


def _create_base_engine() -> AsyncEngine:
    connect_args: dict[str, Any] = {"connect_timeout": 10}

    return create_async_engine(
        _SETTINGS.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


def _create_test_engine() -> AsyncEngine:
    engine = _create_base_engine()

    @event.listens_for(engine.sync_engine, "begin")
    def _set_search_path(connection: Any) -> None:
        connection.exec_driver_sql(f'SET LOCAL search_path TO "{_TEST_SCHEMA_NAME}", public')

    return engine


def _patch_database_modules(test_engine: AsyncEngine) -> None:
    database_engine_module = importlib.import_module("src.database.engine")
    database_session_module = importlib.import_module("src.database.session")

    test_session_maker = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    database_engine_module.engine = test_engine
    database_session_module.engine = test_engine
    database_session_module.async_session_maker = test_session_maker

    for module_name in (
        "src.ai.client",
        "src.ai.rag.service",
        "src.ai.tools.learning.action_tools",
        "src.ai.tools.learning.query_tools",
        "src.books.facade",
        "src.courses.services.course_content_service",
        "src.videos.service",
    ):
        module = sys.modules.get(module_name)
        if module is not None:
            cast("Any", module).async_session_maker = test_session_maker


def _normalize_username(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._]+", "_", value.strip().lower())
    normalized = re.sub(r"[._]{2,}", "_", normalized).strip("._")
    if len(normalized) < 5:
        normalized = f"user_{normalized or 'test'}"
    return normalized[:24]


def _resolve_user_identity(email: str | None) -> tuple[uuid.UUID, str, str]:
    normalized_email = (email or "test-user@example.com").strip().lower()
    user_id = _FIXED_EMAIL_USER_IDS.get(normalized_email)
    if user_id is None:
        user_id = uuid.uuid5(uuid.NAMESPACE_DNS, normalized_email)
    username_source = normalized_email.split("@", 1)[0]
    return user_id, normalized_email, _normalize_username(username_source)


async def _seed_default_user(test_engine: AsyncEngine) -> None:
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        existing_user = await session.get(User, DEFAULT_USER_ID)
        if existing_user is None:
            session.add(
                User(
                    id=DEFAULT_USER_ID,
                    username="default_user",
                    email="default@localhost",
                    password_hash="not_used_in_single_user_mode",  # noqa: S106
                    is_active=True,
                    is_verified=True,
                )
            )
            await session.commit()


async def _ensure_local_user(test_engine: AsyncEngine, *, email: str | None) -> tuple[uuid.UUID, int]:
    user_id, normalized_email, username = _resolve_user_identity(email)

    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        user = await session.get(User, user_id)
        if user is None:
            user = User(
                id=user_id,
                username=username,
                email=normalized_email,
                password_hash="not-used-in-tests",  # noqa: S106
                is_active=True,
                is_verified=True,
            )
            session.add(user)
            await session.flush()
        await session.commit()
        return user.id, user.auth_token_version


async def _create_local_auth_cookie(
    test_engine: AsyncEngine,
    *,
    user_id: uuid.UUID,
    token_version: int,
) -> str:
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        auth_session = await create_auth_session(
            session,
            user_id=user_id,
            expires_at=datetime.max.replace(tzinfo=UTC),
            user_agent="pytest-client",
            ip_address="127.0.0.1",
        )
        await session.commit()
        return create_access_token(user_id, token_version=token_version, session_id=auth_session.id)


async def _truncate_all_tables(test_engine: AsyncEngine) -> None:
    async with test_engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = current_schema()
                  AND tablename <> 'schema_migrations'
                ORDER BY tablename
                """
            )
        )
        tables = [f'"{row[0]}"' for row in result]
        if tables:
            await conn.execute(text(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"))


async def _assert_isolated_test_schema(test_engine: AsyncEngine) -> None:
    async with test_engine.connect() as conn:
        current_schema = (await conn.execute(text("SELECT current_schema()"))).scalar_one()
        users_table_exists = bool(
            (
                await conn.execute(
                    text(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM pg_tables
                            WHERE schemaname = current_schema()
                              AND tablename = 'users'
                        )
                        """
                    )
                )
            ).scalar_one()
        )

        if users_table_exists:
            return

        search_path = (await conn.execute(text("SHOW search_path"))).scalar_one()
        msg = (
            f"Test schema {current_schema} is missing core tables after migration setup; "
            f"search_path={search_path}. Refusing to fall back to public schema."
        )
        raise RuntimeError(msg)


@dataclass(slots=True)
class _ModeAwareClient:
    """Small wrapper that carries auth expectations alongside an AsyncClient."""

    _client: httpx.AsyncClient
    expected_user_id: str
    auth_mode: AuthMode

    def __getattr__(self, name: str) -> Any:
        """Delegate unknown attributes to the wrapped HTTP client."""
        return getattr(self._client, name)

    async def __aenter__(self) -> Self:
        """Support `async with` without re-entering the wrapped client."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        """Leave cleanup to the fixture that owns the underlying client."""
        return False

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        return await self._client.request(method, url, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._client.get(url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._client.post(url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._client.put(url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._client.patch(url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._client.delete(url, **kwargs)


def _discard_detached_task(coro: Any) -> None:
    coro.close()


_configure_test_settings()
_TEST_ENGINE = _create_test_engine()
_patch_database_modules(_TEST_ENGINE)

main_module = importlib.import_module("src.main")

main_module.engine = _TEST_ENGINE
main_module.app = main_module.create_app()


@pytest.fixture(scope="session")
def app() -> Any:
    return main_module.app


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine() -> AsyncIterator[AsyncEngine]:
    admin_engine = _create_base_engine()
    try:
        async with admin_engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{_TEST_SCHEMA_NAME}"'))

        await apply_migrations(_TEST_ENGINE)
        await _assert_isolated_test_schema(_TEST_ENGINE)
        await _seed_default_user(_TEST_ENGINE)
        yield _TEST_ENGINE
    finally:
        await cleanup_litellm_async_clients()
        await _TEST_ENGINE.dispose()
        async with admin_engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{_TEST_SCHEMA_NAME}" CASCADE'))
        await admin_engine.dispose()
        shutil.rmtree(_TEST_STORAGE_PATH, ignore_errors=True)


@pytest_asyncio.fixture(autouse=True)
async def _reset_database_between_tests(test_engine: AsyncEngine) -> AsyncIterator[None]:
    await _truncate_all_tables(test_engine)
    await _seed_default_user(test_engine)
    yield


@pytest.fixture
def auth_mode(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Iterator[AuthMode]:
    mode = getattr(request, "param", AuthMode.SINGLE_USER)
    provider = "none" if mode == AuthMode.SINGLE_USER else "local"

    monkeypatch.setenv("AUTH_PROVIDER", provider)
    _reload_settings().AUTH_PROVIDER = provider
    try:
        yield mode
    finally:
        _reload_settings()


@pytest.fixture
def _auth_mode(auth_mode: AuthMode) -> AuthMode:
    return auth_mode


@pytest.fixture
def mock_external_services(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_video_info(_self: Any, url: str) -> dict[str, Any]:
        await asyncio.sleep(0)
        video_id = url.rsplit("=", 1)[-1] or f"video-{uuid.uuid4().hex[:8]}"
        return {
            "youtube_id": video_id[:20],
            "url": url,
            "title": f"Test Video {video_id[:8]}",
            "channel": "Test Channel",
            "channel_id": "test-channel",
            "duration": 600,
            "thumbnail_url": "https://example.com/thumb.jpg",
            "description": "Integration-test video metadata",
            "tags": ["test"],
            "published_at": None,
        }

    async def noop_async(*_args: Any, **_kwargs: Any) -> None:
        await asyncio.sleep(0)

    monkeypatch.setattr("src.videos.service.VideoService.fetch_video_info", fake_fetch_video_info)
    monkeypatch.setattr("src.videos.service._spawn_detached_task", _discard_detached_task)
    monkeypatch.setattr("src.auth.emails.send_reset_email", noop_async)
    monkeypatch.setattr("src.auth.emails.send_verification_email", noop_async)


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session


@pytest_asyncio.fixture
async def client_factory(
    app: Any,
    auth_mode: AuthMode,
    test_engine: AsyncEngine,
    mock_external_services: None,
) -> AsyncIterator[Any]:
    clients: list[httpx.AsyncClient] = []
    del mock_external_services

    async def factory(email: str | None = None) -> _ModeAwareClient:
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
            follow_redirects=True,
        )
        clients.append(client)

        if auth_mode == AuthMode.SINGLE_USER:
            return _ModeAwareClient(_client=client, expected_user_id=str(DEFAULT_USER_ID), auth_mode=auth_mode)

        user_id, token_version = await _ensure_local_user(test_engine, email=email)
        auth_cookie = await _create_local_auth_cookie(test_engine, user_id=user_id, token_version=token_version)
        client.cookies.set(get_settings().AUTH_COOKIE_NAME, auth_cookie)

        csrf_response = await client.get("/health")
        csrf_response.raise_for_status()
        csrf_token = client.cookies.get("csrftoken")
        if csrf_token:
            client.headers["X-CSRFToken"] = csrf_token

        return _ModeAwareClient(_client=client, expected_user_id=str(user_id), auth_mode=auth_mode)

    yield factory

    for client in clients:
        await client.aclose()


@pytest_asyncio.fixture
async def client(client_factory: Any) -> Any:
    return await client_factory()
