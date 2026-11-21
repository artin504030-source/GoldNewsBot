import logging
from dataclasses import dataclass
from .formatting import format_news
from .models import NewsItem
from .ports import NewsRepository, MessageSender, NewsSource

logger = logging.getLogger(__name__)

@dataclass
class PipelineResult:
    fetched: int = 0
    sent: int = 0
    duplicates: int = 0
    failed: int = 0

class NewsPipeline:
    def __init__(self, source: NewsSource, repository: NewsRepository, sender: MessageSender):
        self.source = source
        self.repository = repository
        self.sender = sender

    def run_once(self) -> PipelineResult:
        result = PipelineResult()
        for item in self.source.fetch():
            result.fetched += 1
            fingerprint = item.fingerprint
            if self.repository.has_seen(fingerprint):
                result.duplicates += 1
                continue
            try:
                self.sender.send(format_news(item))
                self.repository.mark_seen(fingerprint)
                result.sent += 1
            except Exception:
                result.failed += 1
                logger.exception("Failed to process news item from source=%s", item.source)
        return result
