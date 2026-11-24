"""Environment-backed configuration for Gold Market."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    report_interval_minutes: int = 60
    timezone: str = "UTC"

    @classmethod
    def from_env(cls) -> "Settings":
        raw_interval = os.getenv("GOLD_MARKET_INTERVAL_MINUTES", "60")
        try:
            interval = int(raw_interval)
        except ValueError as exc:
            raise ValueError("GOLD_MARKET_INTERVAL_MINUTES must be an integer") from exc
        if interval != 60:
            raise ValueError("Gold Market report interval is fixed at 60 minutes in v1")
        return cls(
            telegram_bot_token=os.getenv("GOLD_MARKET_BOT_TOKEN"),
            telegram_chat_id=os.getenv("GOLD_MARKET_CHAT_ID"),
            report_interval_minutes=interval,
            timezone=os.getenv("GOLD_MARKET_TIMEZONE", "UTC"),
        )

    def validate_telegram(self) -> None:
        missing = []
        if not self.telegram_bot_token:
            missing.append("GOLD_MARKET_BOT_TOKEN")
        if not self.telegram_chat_id:
            missing.append("GOLD_MARKET_CHAT_ID")
        if missing:
            raise ValueError("Missing required environment variables: " + ", ".join(missing))
