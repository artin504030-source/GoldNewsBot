"""Provider-neutral translation orchestration for news title and full body."""
from dataclasses import replace
from .models import NewsItem
from .ports import NewsTranslator


class TranslationError(RuntimeError):
    pass


def translate_news_item(item: NewsItem, translator: NewsTranslator) -> NewsItem:
    """Translate original title and body into Persian without mutating the source."""
    if not item.body.strip():
        raise TranslationError("Original news body is empty; full-text translation cannot proceed")
    title = translator.translate(item.title, target_language="fa").strip()
    if not title:
        raise TranslationError("Translator returned an empty Persian headline")
    translated_body = translator.translate(item.body, target_language="fa").strip()
    if not translated_body:
        raise TranslationError("Translator returned an empty Persian article body")
    return replace(item, translated_title=title, translated_text=translated_body)
