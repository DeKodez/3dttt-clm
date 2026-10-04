"""Environment loader — parses the repo .env without extra dependencies."""

import os
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"


def load_env(path: Optional[Path] = None) -> None:
    """Load KEY=VALUE pairs from .env into os.environ (existing vars win)."""
    env_path = path or ENV_PATH
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def get_env(name: str) -> Optional[str]:
    """Return an environment variable after loading .env, or None if unset."""
    load_env()
    value = os.environ.get(name, "").strip()
    return value or None
