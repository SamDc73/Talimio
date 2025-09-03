"""MDX Service - validation and metadata utilities for MDX content."""

import logging

from mdxjs_py import compile_sync  # type: ignore[attr-defined]


logger = logging.getLogger(__name__)


class MDXService:
    """Service for MDX validation and analysis."""

    def validate_mdx(self, mdx_content: str) -> tuple[bool, str | None]:
        """
        Validate MDX content syntax and structure.

        Parameters
        ----------
        mdx_content : str
            The MDX content to validate

        Returns
        -------
        tuple[bool, Optional[str]]
            (is_valid, error_message)
        """
        try:
            # Use compile_sync just for validation - we don't use the output
            # This ensures the MDX is syntactically correct
            compile_sync(mdx_content, development=False)
            return True, None
        except Exception as e:
            logger.debug("MDX validation failed: %s", str(e))
            return False, str(e)

    def extract_metadata(self, mdx_content: str) -> dict:
        """
        Extract metadata from MDX content.

        Parameters
        ----------
        mdx_content : str
            The MDX content to analyze

        Returns
        -------
        dict
            Metadata about the content
        """
        # Check if content has interactive components
        has_exports = "export " in mdx_content
        has_imports = "import " in mdx_content
        has_jsx_components = "<" in mdx_content and "/>" in mdx_content
        is_interactive = has_exports or has_imports or "useState" in mdx_content or "useEffect" in mdx_content

        return {
            "is_interactive": is_interactive,
            "has_exports": has_exports,
            "has_imports": has_imports,
            "has_jsx_components": has_jsx_components,
            "length": len(mdx_content),
        }


# Singleton instance
mdx_service = MDXService()
