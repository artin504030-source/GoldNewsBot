"""Telegram-safe formatting for Gold Market reports; no network side effects."""
from __future__ import annotations

from html import escape
from datetime import datetime
from typing import Mapping

from .analysis import MarketAssessment
from .models import MarketObservation
from .report import render_market_report

SECTION_HEADINGS = {
    "🟡 گزارش وضعیت بازار طلا",
    "📊 وضعیت بازار",
    "💹 داده‌های بازار و منابع",
    "🌍 زمینه بین‌بازاری",
    "🧭 سناریوها",
    "⚠️ ریسک رویدادها",
    "🔎 هشدارهای کیفیت داده",
}

SIGNATURE_LINES = ("Gold Admin", "Market Admin")


def _telegram_lines(report: str) -> list[str]:
    """Apply the shared channel/title/body layout and escape report content."""
    source_lines = report.splitlines()
    title = source_lines[0].strip() if source_lines else "گزارش وضعیت بازار"
    body_lines = source_lines[1:]
    rendered = [
        "<b>Gold Channel | XAU</b>",
        "",
        "<b>عنوان:</b>",
        escape(title, quote=True),
        "",
        "<b>متن:</b>",
    ]
    for line in body_lines:
        safe = escape(line, quote=True)
        if line in SECTION_HEADINGS:
            rendered.append(f"<b>{safe}</b>")
        else:
            rendered.append(safe)
    rendered.extend(["", *(f"<b>{line}</b>" for line in SIGNATURE_LINES)])
    return rendered


def _split_long_line(line: str, limit: int) -> list[str]:
    """Split an escaped line without cutting an HTML entity in half."""
    if len(line) <= limit:
        return [line]
    pieces: list[str] = []
    current = ""
    i = 0
    while i < len(line):
        if line[i] == "&":
            end = line.find(";", i)
            token = line[i:end + 1] if end != -1 else line[i]
        else:
            token = line[i]
        if current and len(current) + len(token) > limit:
            pieces.append(current)
            current = ""
        current += token
        i += len(token)
    if current:
        pieces.append(current)
    return pieces


def split_telegram_html(lines: list[str], max_length: int = 3900) -> tuple[str, ...]:
    """Pack complete escaped lines into Telegram-sized HTML messages."""
    if max_length < 100:
        raise ValueError("max_length must be at least 100")
    messages: list[str] = []
    current = ""
    for line in lines:
        for part in _split_long_line(line, max_length):
            candidate = part if not current else current + "\n" + part
            if len(candidate) > max_length:
                if current:
                    messages.append(current)
                current = part
            else:
                current = candidate
    if current:
        messages.append(current)
    return tuple(messages)


def render_telegram_report(
    assessment: MarketAssessment,
    observations: Mapping[str, MarketObservation] | None = None,
    generated_at: datetime | None = None,
    max_length: int = 3900,
) -> tuple[str, ...]:
    """Return HTML-formatted Telegram message(s), without sending them."""
    report = render_market_report(assessment, observations, generated_at)
    return split_telegram_html(_telegram_lines(report), max_length=max_length)
