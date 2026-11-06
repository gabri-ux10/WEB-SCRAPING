"""Read only explicitly requested keys from a simple project .env file."""

from __future__ import annotations

from pathlib import Path


def load_selected_env(path: Path, allowed_keys: set[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        candidate = stripped[7:].lstrip() if stripped.startswith("export ") else stripped
        key, separator, raw = candidate.partition("=")
        key = key.strip()
        if not separator or key not in allowed_keys:
            continue
        value = raw.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values
