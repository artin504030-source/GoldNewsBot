"""Database adapter exports. SQLite is the safe local/staging default for phase 1."""
from goldnewsbot.storage import SQLiteNewsRepository

__all__ = ["SQLiteNewsRepository"]
