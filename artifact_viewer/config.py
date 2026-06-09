from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(slots=True)
class Settings:
    app_name: str = "Artifact Viewer"
    db_path: Path = Path(os.getenv("ARTIFACT_DB_PATH", "./data/artifacts.db"))
    base_url: str | None = os.getenv("BASE_URL")
    cleanup_interval_seconds: int = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "30"))
    default_ttl_minutes: int = int(os.getenv("DEFAULT_TTL_MINUTES", "60"))
    max_ttl_minutes: int = int(os.getenv("MAX_TTL_MINUTES", str(7 * 24 * 60)))

    def ensure_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
