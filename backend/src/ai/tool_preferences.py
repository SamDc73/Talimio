"""In-memory tracking of per-user MCP tool helpfulness."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID


@dataclass(slots=True)
class ToolPreference:
    """Aggregate counters describing how helpful a tool has been."""

    successes: int = 0
    failures: int = 0
    last_used: datetime | None = None

    @property
    def success_rate(self) -> float:
        """Return the ratio of successful calls to total invocations."""
        total = self.successes + self.failures
        if total == 0:
            return 0.0
        return self.successes / total


_PREFERENCES: dict[UUID, dict[str, ToolPreference]] = {}
_LOCK = threading.Lock()


def record_tool_helpfulness(user_id: UUID | None, tool_name: str, success: bool) -> None:
    """Update per-user stats after an MCP tool run."""
    if user_id is None:
        return
    normalized = tool_name.strip()
    if not normalized:
        return
    with _LOCK:
        user_stats = _PREFERENCES.setdefault(user_id, {})
        pref = user_stats.setdefault(normalized, ToolPreference())
        if success:
            pref.successes += 1
        else:
            pref.failures += 1
        pref.last_used = datetime.now(UTC)


def build_preference_hint(user_id: UUID | None) -> str | None:
    """Summarize top/bottom tools for use in prompt hints."""
    if user_id is None:
        return None
    stats = _PREFERENCES.get(user_id)
    if not stats:
        return None
    best_tool: tuple[str, ToolPreference] | None = None
    worst_tool: tuple[str, ToolPreference] | None = None
    for name, pref in stats.items():
        if best_tool is None or pref.success_rate > best_tool[1].success_rate:
            best_tool = (name, pref)
        if worst_tool is None or pref.failures > worst_tool[1].failures:
            worst_tool = (name, pref)
    hints: list[str] = []
    if best_tool and best_tool[1].successes > best_tool[1].failures:
        hints.append(f"Leans on {best_tool[0]} ({best_tool[1].successes} good runs)")
    if (
        worst_tool
        and worst_tool[1].failures > worst_tool[1].successes
        and (not best_tool or worst_tool[0] != best_tool[0])
    ):
        hints.append(f"Prefers to avoid {worst_tool[0]} ({worst_tool[1].failures} misses)")
    if not hints:
        return None
    return "; ".join(hints)


def preference_rank(user_id: UUID | None, tool_name: str) -> float:
    """Return a sorting key that pushes preferred tools to the top."""
    if user_id is None:
        return 0.0
    stats = _PREFERENCES.get(user_id)
    if not stats:
        return 0.0
    pref = stats.get(tool_name)
    if pref is None:
        return 0.0
    return -pref.success_rate
