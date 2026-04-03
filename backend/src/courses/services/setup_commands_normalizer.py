"""Normalize course setup commands for E2B sandbox compatibility."""

import json
import shlex
from typing import Any


_GLOBAL_INSTALL_FLAGS = {"-g", "--global"}
_APT_COMMANDS = {"apt", "apt-get"}
_CPP_TOOLCHAIN_PACKAGES = {
    "build-essential",
    "clang",
    "clang++",
    "cmake",
    "g++",
    "gcc",
    "make",
}
_RUSTUP_SCRIPT_MARKER = "sh.rustup.rs"
_RUSTUP_APT_COMMAND = "apt-get update && apt-get install -y --no-install-recommends rustc cargo"


def normalize_setup_commands_payload(value: Any) -> list[str]:
    """Normalize setup_commands payloads from list/scalar/json-string sources."""
    return normalize_setup_commands(_coerce_setup_commands(value))


def normalize_setup_commands(commands: list[str]) -> list[str]:
    """Normalize setup command strings while preserving order."""
    normalized: list[str] = []
    for command in commands:
        candidate = command.strip()
        if not candidate:
            continue
        updated = _normalize_single_command(candidate)
        if updated:
            normalized.append(updated)
    return normalized


def _coerce_setup_commands(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    text_value = str(value).strip() if not isinstance(value, str) else value.strip()
    if not text_value:
        return []

    if text_value.startswith("["):
        try:
            parsed = json.loads(text_value)
        except json.JSONDecodeError:
            return [text_value]
        return _coerce_setup_commands(parsed)

    return [text_value]


def _normalize_single_command(command: str) -> str:
    if _RUSTUP_SCRIPT_MARKER in command.lower():
        return _RUSTUP_APT_COMMAND

    segments = [segment.strip() for segment in command.split("&&") if segment.strip()]
    if not segments:
        return command

    if len(segments) == 2:
        first_tokens = _canonicalize_apt_tokens(_safe_split(segments[0]))
        second_tokens = _canonicalize_apt_tokens(_safe_split(segments[1]))
        apt_packages = _extract_apt_install_packages(second_tokens)
        if _is_apt_update_tokens(first_tokens) and apt_packages and all(pkg in _CPP_TOOLCHAIN_PACKAGES for pkg in apt_packages):
            return _cpp_runtime_check_command()

    normalized_segments = [_normalize_segment(segment) for segment in segments]
    return " && ".join(normalized_segments)


def _normalize_segment(segment: str) -> str:
    tokens = _safe_split(segment)
    if not tokens:
        return segment

    canonical_tokens = _canonicalize_apt_tokens(tokens)

    node_tokens = _normalize_node_install(canonical_tokens)
    if node_tokens is not None:
        return shlex.join(node_tokens)

    pip_tokens = _normalize_pip_install(canonical_tokens)
    if pip_tokens is not None:
        return shlex.join(pip_tokens)

    apt_packages = _extract_apt_install_packages(canonical_tokens)
    if apt_packages and all(pkg in _CPP_TOOLCHAIN_PACKAGES for pkg in apt_packages):
        return _cpp_runtime_check_command()

    if canonical_tokens != tokens:
        return shlex.join(canonical_tokens)

    return segment


def _normalize_node_install(tokens: list[str]) -> list[str] | None:
    first = tokens[0]
    if first == "npm" and len(tokens) >= 2 and tokens[1] in {"install", "i"}:
        return _strip_global_flags(tokens)
    if first == "pnpm" and len(tokens) >= 2 and tokens[1] in {"install", "add", "i"}:
        return _strip_global_flags(tokens)
    if first == "yarn" and len(tokens) >= 3 and tokens[1] == "global" and tokens[2] == "add":
        return _strip_global_flags(["yarn", "add", *tokens[3:]])
    if first == "yarn" and len(tokens) >= 2 and tokens[1] in {"add", "install"}:
        return _strip_global_flags(tokens)
    return None


def _normalize_pip_install(tokens: list[str]) -> list[str] | None:
    if tokens[0] in {"pip", "pip3"} and len(tokens) >= 2 and tokens[1] == "install":
        return _strip_global_flags(tokens)

    is_python_module_pip_install = (
        len(tokens) >= 4
        and tokens[0] in {"python", "python3"}
        and tokens[1] == "-m"
        and tokens[2] == "pip"
        and tokens[3] == "install"
    )
    if is_python_module_pip_install:
        return _strip_global_flags(tokens)

    return None


def _canonicalize_apt_tokens(tokens: list[str]) -> list[str]:
    if not tokens:
        return tokens

    normalized = list(tokens)
    if len(normalized) >= 2 and normalized[0] == "sudo" and normalized[1] in _APT_COMMANDS:
        normalized = normalized[1:]

    if len(normalized) >= 2 and normalized[0] == "apt" and normalized[1] in {"update", "install"}:
        normalized[0] = "apt-get"

    is_apt_install = len(normalized) >= 2 and normalized[0] == "apt-get" and normalized[1] == "install"
    has_assume_yes_flag = any(token in {"-y", "--yes", "--assume-yes"} for token in normalized[2:])
    if is_apt_install and not has_assume_yes_flag:
        normalized.insert(2, "-y")

    return normalized


def _strip_global_flags(tokens: list[str]) -> list[str]:
    return [token for token in tokens if token not in _GLOBAL_INSTALL_FLAGS]


def _extract_apt_install_packages(tokens: list[str]) -> set[str]:
    if not tokens or tokens[0] not in _APT_COMMANDS:
        return set()
    if "install" not in tokens:
        return set()

    install_index = tokens.index("install")
    return {
        token.split("=", maxsplit=1)[0].lower()
        for token in tokens[install_index + 1 :]
        if token and not token.startswith("-")
    }


def _is_apt_update_tokens(tokens: list[str]) -> bool:
    return len(tokens) >= 2 and tokens[0] in _APT_COMMANDS and tokens[1] == "update"


def _cpp_runtime_check_command() -> str:
    return "command -v g++ >/dev/null || command -v clang++ >/dev/null"


def _safe_split(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return []
