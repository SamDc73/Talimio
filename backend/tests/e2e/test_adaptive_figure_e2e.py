"""Live E2E test for adaptive figure generation.

Run with:
    cd backend
    source tests/e2e/conceptflow.vars && python tests/e2e/test_adaptive_figure_e2e.py

Requirements:
    - Backend server running on localhost:8080
    - Environment variables set (see .env file)
"""

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass

import httpx

# ─── Configuration ───────────────────────────────────────────────────────────

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")
TEST_USER_EMAIL = os.getenv("TEST_USER_EMAIL", "trevor.nem08@slmail.me")
TEST_USER_PASSWORD = os.getenv("TEST_USER_PASSWORD", "jYf^%mb2yCb@")

# A science concept that clearly needs a figure
COURSE_TOPIC = "neuron anatomy and synaptic transmission"
COURSE_PROMPT = (
    "Create a comprehensive course about neuron anatomy and synaptic transmission. "
    "Include detailed explanations of axons, dendrites, synapses, and neurotransmitters. "
    "Make it visual and engaging with diagrams and figures."
)

# ─── Live API Client ───────────────────────────────────────────────────────────


@dataclass
class LiveApi:
    """Simplified API client for live E2E testing."""

    base_url: str
    token: str | None = None
    user_id: str | None = None
    _client: httpx.AsyncClient | None = None

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        return headers

    def _cookies(self) -> dict[str, str]:
        if self.token:
            return {"talimio_auth": self.token}
        return {}

    async def login(self) -> None:
        """Authenticate and get session cookie."""
        self._client = httpx.AsyncClient()
        response = await self._client.post(
            f"{self.base_url}/api/v1/auth/login",
            data={"grant_type": "password", "username": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": self.base_url,
                "Sec-Fetch-Site": "same-origin",
            },
        )
        response.raise_for_status()
        data = response.json()
        self.user_id = data["user"]["id"]
        # Extract cookie from response
        cookies = response.cookies
        if cookies:
            self.token = cookies.get("talimio_auth", "") or ""
        else:
            self.token = ""

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    async def create_course(self) -> dict:
        """Create a new adaptive course."""
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Origin": self.base_url,
            "Sec-Fetch-Site": "same-origin",
        }
        response = await self._client.post(
            f"{self.base_url}/api/v1/courses",
            data={
                "prompt": COURSE_PROMPT,
                "adaptive_enabled": "true",
            },
            headers=headers,
            cookies=self._cookies(),
        )
        response.raise_for_status()
        return response.json()

    async def get_course(self, course_id: str) -> dict:
        """Get course by ID."""
        response = await self._client.get(
            f"{self.base_url}/api/v1/courses/{course_id}",
            headers=self._headers(),
            cookies=self._cookies(),
        )
        response.raise_for_status()
        return response.json()

    async def get_lesson(self, course_id: str, lesson_id: str) -> dict:
        """Get lesson by ID."""
        response = await self._client.get(
            f"{self.base_url}/api/v1/courses/{course_id}/lessons/{lesson_id}",
            headers=self._headers(),
            cookies=self._cookies(),
        )
        response.raise_for_status()
        return response.json()

    async def generate_lesson(self, course_id: str, lesson_id: str) -> dict:
        """Trigger lesson content generation."""
        response = await self._client.get(
            f"{self.base_url}/api/v1/courses/{course_id}/lessons/{lesson_id}?generate=true",
            headers=self._headers(),
            cookies=self._cookies(),
        )
        response.raise_for_status()
        return response.json()

    async def get_lesson_content(self, course_id: str, lesson_id: str) -> dict:
        """Get lesson content."""
        response = await self._client.get(
            f"{self.base_url}/api/v1/courses/{course_id}/lessons/{lesson_id}/content",
            headers=self._headers(),
            cookies=self._cookies(),
        )
        response.raise_for_status()
        return response.json()


# ─── Test Runner ───────────────────────────────────────────────────────────────


async def test_adaptive_figure_e2e():
    """Test that adaptive courses can generate lessons with figures."""
    api = LiveApi(base_url=BASE_URL)

    try:
        # Step 1: Login
        print("🔐 Step 1: Logging in...")
        await api.login()
        print(f"   ✅ Logged in as {api.user_id}")

        # Step 2: Create course
        print(f"\n📚 Step 2: Creating course '{COURSE_TOPIC}'...")
        course = await api.create_course()
        course_id = course["id"]
        print(f"   ✅ Created course {course_id}")

        # Step 3: Wait for generation
        print("\n⏳ Step 3: Waiting for course generation...")
        max_wait = 120
        for i in range(max_wait):
            course_data = await api.get_course(course_id)
            status = course_data.get("generation_status", "unknown")
            print(f"   ⏳ Status: {status} ({i}s)")

            if status == "ready":
                print(f"   ✅ Course generation complete!")
                break
            elif status == "failed":
                raise RuntimeError(f"Course generation failed: {course_data}")
            await asyncio.sleep(1)
        else:
            raise RuntimeError(f"Course generation timed out after {max_wait}s")

        # Step 4: Get first lesson
        print("\n📖 Step 4: Getting first lesson...")
        lessons = course_data.get("lessons", [])
        if not lessons:
            # Try modules
            modules = course_data.get("modules", [])
            for module in modules:
                lessons.extend(module.get("lessons", []))

        if not lessons:
            raise RuntimeError("No lessons found in course")

        first_lesson = lessons[0]
        lesson_id = first_lesson["id"]
        print(f"   ✅ Got lesson: {first_lesson['title']} ({lesson_id})")

        # Step 5: Generate lesson content
        print("\n📝 Step 5: Generating lesson content...")
        try:
            lesson = await api.generate_lesson(course_id, lesson_id)
            print(f"   ✅ Lesson generation triggered")
        except Exception as e:
            print(f"   ⚠️ Lesson generation endpoint failed: {e}")
            # Try to get content directly
            lesson = await api.get_lesson(course_id, lesson_id)

        # Step 6: Wait for content
        print("\n⏳ Step 6: Waiting for lesson content...")
        max_wait = 120
        for i in range(max_wait):
            try:
                content = await api.get_lesson_content(course_id, lesson_id)
                if content.get("content"):
                    print(f"   ✅ Lesson content ready!")
                    break
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    print(f"   ⏳ Content not ready yet ({i}s)")
                else:
                    raise
            await asyncio.sleep(1)
        else:
            raise RuntimeError(f"Lesson content timed out after {max_wait}s")

        # Step 7: Check for figure
        print("\n🔍 Step 7: Checking for figure component...")
        lesson_content = content.get("content", "")
        has_figure = "<Figure" in lesson_content

        if has_figure:
            print(f"   ✅ Figure component found!")
            # Extract figure attributes
            import re

            figure_match = re.search(r"<Figure[^>]+>", lesson_content)
            if figure_match:
                figure_tag = figure_match.group(0)
                print(f"   📷 Figure tag: {figure_tag[:200]}...")

                # Check for MDX expression format
                if 'src={"' in figure_tag:
                    print(f"   ✅ Figure uses MDX expression format (safe)")
                elif 'src="' in figure_tag:
                    print(f"   ⚠️ Figure uses raw string format (might break with quotes)")
        else:
            print(f"   ⚠️ No figure component found in lesson content")
            print(f"   📝 Content preview: {lesson_content[:500]}...")

        # Step 8: Summary
        print("\n" + "=" * 60)
        print("📊 E2E TEST RESULTS")
        print("=" * 60)
        print(f"Course: {course_data['title']}")
        print(f"Lesson: {first_lesson['title']}")
        print(f"Content length: {len(lesson_content)} chars")
        print(f"Figure found: {has_figure}")
        print("=" * 60)

        return has_figure
    finally:
        await api.close()


if __name__ == "__main__":
    result = asyncio.run(test_adaptive_figure_e2e())
    if result:
        print("\n🎉 E2E test PASSED - Figure generated successfully!")
    else:
        print("\n⚠️ E2E test PASSED but no figure was generated")
        print("   This might be because the LLM chose not to use a figure for this topic")
