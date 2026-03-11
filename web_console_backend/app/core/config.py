import os
from dataclasses import dataclass
from pathlib import Path

from functools import lru_cache


REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(slots=True)
class Settings:
    app_name: str
    env: str
    debug: bool
    host: str
    port: int
    config_path: Path
    runs_dir: Path
    database_url: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    config_path = Path(os.getenv("WEB_CONSOLE_CONFIG_PATH", "config.json"))
    runs_dir = Path(os.getenv("WEB_CONSOLE_RUNS_DIR", "runs/projects"))

    if not config_path.is_absolute():
        config_path = REPO_ROOT / config_path

    if not runs_dir.is_absolute():
        runs_dir = REPO_ROOT / runs_dir

    return Settings(
        app_name=os.getenv("WEB_CONSOLE_APP_NAME", "Story Video Console"),
        env=os.getenv("WEB_CONSOLE_ENV", "development"),
        debug=os.getenv("WEB_CONSOLE_DEBUG", "true").strip().lower() in {"1", "true", "yes", "on"},
        host=os.getenv("WEB_CONSOLE_HOST", "127.0.0.1"),
        port=int(os.getenv("WEB_CONSOLE_PORT", "8000")),
        config_path=config_path,
        runs_dir=runs_dir,
        database_url=os.getenv(
            "WEB_CONSOLE_DATABASE_URL",
            "mysql+pymysql://root:password@127.0.0.1:3306/story_video_console",
        ),
    )
