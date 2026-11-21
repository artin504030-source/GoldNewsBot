from dataclasses import dataclass
import os
from pathlib import Path

@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    log_level: str = "INFO"
    database_path: Path = Path("data/goldnewsbot.sqlite3")
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_parse_mode: str = "HTML"

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.getenv("APP_ENV", "development").strip().lower()
        level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        if env not in {"development", "test", "staging", "production"}:
            raise ValueError("APP_ENV must be development, test, staging, or production")
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL is invalid")
        parse_mode = os.getenv("TELEGRAM_PARSE_MODE", "HTML").strip().upper()
        if parse_mode not in {"HTML", "MARKDOWN", "MARKDOWNV2"}:
            raise ValueError("TELEGRAM_PARSE_MODE is invalid")
        return cls(
            app_env=env,
            log_level=level,
            database_path=Path(os.getenv("DATABASE_PATH", "data/goldnewsbot.sqlite3")),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
            telegram_parse_mode=parse_mode,
        )

    @property
    def telegram_ready(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)
