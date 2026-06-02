from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "job_skill_radar.sqlite"
_ENV_LOADED = False


def load_env_file(path: Path | None = None) -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.exists():
        _ENV_LOADED = True
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
    _ENV_LOADED = True


def get_work24_auth_key() -> str:
    load_env_file()
    return os.environ.get("WORK24_AUTH_KEY", "").strip()


def get_db_path() -> Path:
    load_env_file()
    raw_path = os.environ.get("JOB_RADAR_DB_PATH", "").strip()
    if raw_path:
        path = Path(raw_path)
        if path.is_absolute():
            return path
        return PROJECT_ROOT / path
    return DEFAULT_DB_PATH
