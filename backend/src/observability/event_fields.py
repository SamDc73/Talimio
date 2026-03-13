"""Shared event-field derivation helpers for observability and logging."""


def get_feature_area(route: str) -> str:
    """Derive a coarse feature area from /api/v1/<feature>/... paths."""
    parts = [part for part in route.split("/") if part]
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
        return parts[2]
    return "app"
