from typing import Protocol, Iterable
from .models import NewsItem


class NewsSource(Protocol):
    def fetch(self) -> Iterable[NewsItem]: ...


class NewsRepository(Protocol):
    def has_seen(self, fingerprint: str) -> bool: ...
    def mark_seen(self, fingerprint: str) -> None: ...


class MessageSender(Protocol):
    def send(self, text: str) -> None: ...


class NewsTranslator(Protocol):
    """Provider-neutral translation boundary; implementations may use AI or MT."""
    def translate(self, text: str, *, target_language: str = "fa") -> str: ...
