"""Function registry system for AI function calling.

This module implements a function registry system following OpenAI/MCP patterns
for clean function registration and execution.
"""

import json
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any
from uuid import UUID


logger = logging.getLogger(__name__)

# Global registry to store all registered functions
_FUNCTION_REGISTRY: dict[str, dict[str, Any]] = {}


def register_function(schema: dict[str, Any]) -> Callable:
    """Register a function with its OpenAI function schema.

    Args:
        schema: OpenAI function schema definition

    Returns
    -------
        Decorated function

    Example:
        @register_function({
            "type": "function",
            "name": "search_existing_content",
            "description": "Search database for existing content",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic to search for"}
                },
                "required": ["topic"],
                "additionalProperties": False
            },
            "strict": True
        })
        async def search_existing_content(topic: str) -> Dict[str, Any]:
            # Implementation here
            pass
    """

    def decorator(func: Callable) -> Callable:
        function_name = schema.get("name")
        if not function_name:
            msg = "Function schema must include 'name' field"
            raise ValueError(msg)

        # Store function and schema in registry
        _FUNCTION_REGISTRY[function_name] = {"schema": schema, "function": func, "name": function_name}

        logger.info(f"Registered function: {function_name}")

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def get_function_schemas() -> list[dict[str, Any]]:
    """Get all registered function schemas for OpenAI API.

    Returns
    -------
        List of function schemas compatible with OpenAI tools format
    """
    return [entry["schema"] for entry in _FUNCTION_REGISTRY.values()]


def get_function_names() -> list[str]:
    """Get list of all registered function names.

    Returns
    -------
        List of function names
    """
    return list(_FUNCTION_REGISTRY.keys())


async def execute_function(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Execute a registered function with error handling.

    Args:
        name: Function name to execute
        args: Function arguments

    Returns
    -------
        Function result or error information with success flag
    """
    if name not in _FUNCTION_REGISTRY:
        available_functions = ", ".join(_FUNCTION_REGISTRY.keys())
        return {
            "success": False,
            "error": f"Function '{name}' not found. Available: {available_functions}",
            "function_name": name,
        }

    function_entry = _FUNCTION_REGISTRY[name]
    func = function_entry["function"]

    try:
        # Fix user_id if it's "guest" string (AI model sometimes passes this incorrectly)
        if "user_id" in args and isinstance(args["user_id"], str):
            if args["user_id"].lower() == "guest":
                from src.auth.config import DEFAULT_USER_ID

                args["user_id"] = DEFAULT_USER_ID
                logger.info(f"Converted 'guest' string to DEFAULT_USER_ID: {DEFAULT_USER_ID}")
            else:
                # Try to convert string UUID to UUID object
                try:
                    args["user_id"] = UUID(args["user_id"])
                except ValueError:
                    logger.warning(f"Invalid user_id format: {args['user_id']}, setting to None")
                    args["user_id"] = None

        logger.info(f"Executing function: {name} with args: {json.dumps(args, default=str, indent=2)}")

        # Call the function with unpacked arguments
        result = await func(**args)

        logger.info(f"Function {name} executed successfully")
        return {"success": True, "result": result, "function_name": name}

    except Exception as e:
        logger.exception(f"Error executing function {name}: {e!s}")
        return {"success": False, "error": str(e), "function_name": name}


def get_function_info(name: str) -> dict[str, Any] | None:
    """Get information about a registered function.

    Args:
        name: Function name

    Returns
    -------
        Function information or None if not found
    """
    return _FUNCTION_REGISTRY.get(name)


def clear_registry() -> None:
    """Clear all registered functions (mainly for testing)."""
    global _FUNCTION_REGISTRY  # noqa: PLW0603
    _FUNCTION_REGISTRY = {}
    logger.info("Function registry cleared")


def get_registry_status() -> dict[str, Any]:
    """Get current registry status for monitoring.

    Returns
    -------
        Registry status information
    """
    return {
        "total_functions": len(_FUNCTION_REGISTRY),
        "function_names": list(_FUNCTION_REGISTRY.keys()),
        "schemas_valid": all(
            "name" in entry["schema"] and "description" in entry["schema"] for entry in _FUNCTION_REGISTRY.values()
        ),
    }
