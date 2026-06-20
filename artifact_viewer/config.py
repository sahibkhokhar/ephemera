from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DAY_MINUTES = 24 * 60


@dataclass(slots=True)
class Settings:
    """Runtime configuration.

    Defaults are plain literals (not env reads) so the dataclass is trivial to
    construct in tests. Production wiring goes through :meth:`from_env`.
    """

    app_name: str = "Ephemera"
    db_path: Path = Path("./data/artifacts.db")
    base_url: str | None = None
    api_key: str | None = None
    cleanup_interval_seconds: int = 60
    default_ttl_minutes: int = 60
    max_ttl_minutes: int = 7 * DAY_MINUTES
    max_content_bytes: int = 5 * 1024 * 1024  # 5 MiB

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "Settings":
        env = environ if environ is not None else os.environ
        return cls(
            app_name=env.get("APP_NAME", "Ephemera"),
            db_path=Path(env.get("ARTIFACT_DB_PATH", "./data/artifacts.db")),
            base_url=(env.get("BASE_URL") or None),
            api_key=(env.get("API_KEY") or None),
            cleanup_interval_seconds=int(env.get("CLEANUP_INTERVAL_SECONDS", "60")),
            default_ttl_minutes=int(env.get("DEFAULT_TTL_MINUTES", "60")),
            max_ttl_minutes=int(env.get("MAX_TTL_MINUTES", str(7 * DAY_MINUTES))),
            max_content_bytes=int(env.get("MAX_CONTENT_BYTES", str(5 * 1024 * 1024))),
        )

    def ensure_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
