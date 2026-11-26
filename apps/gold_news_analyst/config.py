from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    token: str
    chat_id: str
    archive_path: str = "news_archive.json"
    state_path: str = "gold_news_analyst_state.json"
    max_age_hours: int = 24
    min_relevance: int = 25
    max_items: int = 2
    dry_run: bool = False
    article_fetch: bool = True

    @classmethod
    def from_env(cls):
        token = os.getenv("GOLD_NEWS_ANALYST_BOT_TOKEN", "").strip()
        chat_id = os.getenv("CHANNEL_ID", "").strip()
        if not token or not chat_id:
            raise ValueError("Missing GOLD_NEWS_ANALYST_BOT_TOKEN or CHANNEL_ID")
        return cls(token, chat_id,
            os.getenv("GOLD_NEWS_ARCHIVE_PATH", "news_archive.json"),
            os.getenv("GOLD_NEWS_ANALYST_STATE_PATH", "gold_news_analyst_state.json"),
            max(1, min(168, int(os.getenv("GOLD_NEWS_ANALYST_MAX_AGE_HOURS", "24")))),
            max(0, min(100, int(os.getenv("GOLD_NEWS_ANALYST_MIN_RELEVANCE", "25")))),
            max(1, min(5, int(os.getenv("GOLD_NEWS_ANALYST_MAX_ITEMS", "2")))),
            os.getenv("DRY_RUN", "false").lower() == "true",
            os.getenv("GOLD_NEWS_ANALYST_FETCH_ARTICLES", "true").lower() == "true")
