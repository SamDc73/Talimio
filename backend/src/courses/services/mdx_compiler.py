"""MDX Compilation Service - Compiles MDX to JavaScript on the backend."""

import hashlib
import json
import logging
from pathlib import Path

import aiofiles


logger = logging.getLogger(__name__)


class MDXCompiler:
    """Compiles MDX content to JavaScript for instant frontend rendering."""

    def __init__(self):
        self.compile_endpoint = "http://localhost:3001/compile"  # We'll create a Node service
        self.cache_dir = Path("/tmp/mdx_cache")
        self.cache_dir.mkdir(exist_ok=True)

    def get_cache_key(self, content: str) -> str:
        """Generate cache key from content hash."""
        return hashlib.sha256(content.encode()).hexdigest()

    async def get_cached(self, content: str) -> str | None:
        """Get cached compiled JS if available."""
        cache_key = self.get_cache_key(content)
        cache_file = self.cache_dir / f"{cache_key}.js"

        if cache_file.exists():
            async with aiofiles.open(cache_file) as f:
                return await f.read()
        return None

    async def save_cache(self, content: str, compiled_js: str) -> None:
        """Save compiled JS to cache."""
        cache_key = self.get_cache_key(content)
        cache_file = self.cache_dir / f"{cache_key}.js"

        async with aiofiles.open(cache_file, "w") as f:
            await f.write(compiled_js)

    async def compile(self, mdx_content: str) -> tuple[str, bool]:
        """
        Compile MDX to JavaScript.

        Returns
        -------
            Tuple of (compiled_js, is_interactive)
        """
        # Check cache first
        cached = await self.get_cached(mdx_content)
        if cached:
            logger.info("Using cached MDX compilation")
            is_interactive = "export function" in mdx_content or "React.useState" in mdx_content
            return cached, is_interactive

        # Check if content has interactive components
        is_interactive = (
            "export function" in mdx_content or "React.useState" in mdx_content or "React.useEffect" in mdx_content
        )

        try:
            # For now, return a placeholder - we'll implement the Node service next
            # In production, this would call a Node.js service that compiles MDX
            logger.info("Compiling MDX on backend (placeholder for now)")

            # For testing, just return the original content with a flag
            compiled_js = json.dumps(
                {
                    "type": "mdx_compiled",
                    "interactive": is_interactive,
                    "source": mdx_content,
                    "compiled": None,  # Will be actual compiled JS from Node service
                }
            )

            # Save to cache
            await self.save_cache(mdx_content, compiled_js)

            return compiled_js, is_interactive

        except Exception as e:
            logger.error(f"Failed to compile MDX: {e}")
            # Fallback to returning raw MDX
            return json.dumps({"type": "mdx_raw", "interactive": False, "source": mdx_content, "compiled": None}), False


# Singleton instance
mdx_compiler = MDXCompiler()
