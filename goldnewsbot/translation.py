"""Provider-neutral translation orchestration for news title and full body."""
from dataclasses import replace
from .models import NewsItem
from .ports import NewsTranslator


class TranslationError(RuntimeError):
    pass


def translate_news_item(item: NewsItem, translator: NewsTranslator) -> NewsItem:
    """Return a translated copy; never mutate the original item or invent fallback text."""
    title = translator.translate(item.title, target_language="fa").strip()
    if not title:
        raise TranslationError("Translator returned an empty Persian headline")
    body = item.translated_text.strip()
    if not body:
        raise TranslationError("News body is empty; full-text translation cannot proceed")
    translated_body = translator.translate(body, target_language="fa").strip()
    if not translated_body:
        raise TranslationError("Translator returned an empty Persian article body")
    return replace(item, translated_title=title, translated_text=translated_body)
