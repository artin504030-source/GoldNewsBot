from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    source: str
    published_at: datetime | None = None
    translated_text: str = ""
    analysis: str = ""
    category: str = "general"
    impact_instruments: tuple[str, ...] = ()
    translated_title: str = ""
    body: str = ""

    def __post_init__(self):
        if not self.title.strip():
            raise ValueError("News title cannot be empty")
        if not self.url.startswith(("https://", "http://")):
            raise ValueError("News URL must be HTTP or HTTPS")
        if not self.source.strip():
            raise ValueError("News source cannot be empty")

    @property
    def fingerprint(self) -> str:
        canonical = self.url.strip().lower() or self.title.strip().lower()
        return sha256(canonical.encode("utf-8")).hexdigest()

    @property
    def created_at(self) -> datetime:
        return datetime.now(timezone.utc)
