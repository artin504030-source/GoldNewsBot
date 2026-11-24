"""Environment-backed Gold Market configuration."""
from __future__ import annotations
import os
from dataclasses import dataclass
@dataclass(frozen=True)
class Settings:
    telegram_bot_token:str|None
    telegram_chat_id:str|None
    fred_api_key:str|None=None
    report_interval_minutes:int=60
    timezone:str="UTC"
    @classmethod
    def from_env(cls):
        try: interval=int(os.getenv("GOLD_MARKET_INTERVAL_MINUTES","60"))
        except ValueError as e: raise ValueError("GOLD_MARKET_INTERVAL_MINUTES must be an integer") from e
        if interval!=60: raise ValueError("Gold Market interval is fixed at 60 minutes in v1")
        return cls(os.getenv("GOLD_MARKET_BOT_TOKEN"),os.getenv("GOLD_MARKET_CHAT_ID"),os.getenv("FRED_API_KEY"),interval,os.getenv("GOLD_MARKET_TIMEZONE","UTC"))
    def validate_telegram(self):
        missing=[k for k,v in (("GOLD_MARKET_BOT_TOKEN",self.telegram_bot_token),("GOLD_MARKET_CHAT_ID",self.telegram_chat_id)) if not v]
        if missing: raise ValueError("Missing required environment variables: "+", ".join(missing))
