"""Persian, human-readable Gold Market report rendering (no Telegram side effects)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Mapping

from .analysis import MarketAssessment
from .models import MarketObservation

STATUS_FA = {
    "LIVE": "زنده",
    "DELAYED": "با تأخیر",
    "DAILY": "روزانه",
    "STALE": "قدیمی",
    "UNAVAILABLE": "در دسترس نیست",
}
LABEL_FA = {
    "XAUUSD": "طلا (XAU/USD)",
    "DXY": "شاخص دلار",
    "US10Y": "بازده اوراق ۱۰ساله آمریکا",
    "US02Y": "بازده اوراق ۲ساله آمریکا",
    "USOIL": "نفت WTI",
    "SPX": "شاخص S&P 500",
    "VIX": "شاخص نوسان VIX",
}
DRIVER_FA = {
    "HEADWIND_FOR_GOLD": "فشار بالقوه بر طلا",
    "SUPPORTIVE_FOR_GOLD": "حمایت بالقوه از طلا",
    "NEUTRAL": "خنثی",
    "INFLATION_CONTEXT_UP": "زمینه تورمی؛ افزایش",
    "INFLATION_CONTEXT_DOWN": "زمینه تورمی؛ کاهش",
    "RISK_APPETITE_UP": "افزایش تمایل به ریسک",
    "RISK_APPETITE_DOWN": "کاهش تمایل به ریسک",
    "RISK_AVERSION_HIGHER": "ریسک‌گریزی بیشتر",
    "RISK_AVERSION_LOWER": "ریسک‌گریزی کمتر",
    "RISK_AVERSION_STABLE": "ریسک‌گریزی تقریباً ثابت",
    "UNKNOWN": "نامشخص",
}


def _price(value: Decimal | None) -> str:
    return "نامشخص" if value is None else f"{value:,.2f}"


def _time(value: datetime | None) -> str:
    if value is None:
        return "نامشخص"
    if value.tzinfo is None:
        return value.isoformat()
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _assessment_value(value: Decimal | None, suffix: str = "") -> str:
    return "نامشخص" if value is None else f"{value:,.2f}{suffix}"


def render_market_report(
    assessment: MarketAssessment,
    observations: Mapping[str, MarketObservation] | None = None,
    generated_at: datetime | None = None,
) -> str:
    """Render an assessment and its source observations as a Persian report."""
    observations = observations or {}
    generated_at = generated_at or datetime.now(timezone.utc)
    trend = assessment.trend
    trend_fa = {"BULLISH": "صعودی", "BEARISH": "نزولی", "RANGE": "خنثی / رنج",
                "UNAVAILABLE": "قابل ارزیابی نیست"}.get(trend, trend)
    volatility_fa = {"HIGH": "زیاد", "NORMAL": "معمولی", "LOW": "کم",
                     "UNAVAILABLE": "نامشخص"}.get(assessment.volatility, assessment.volatility)
    confidence_fa = {"HIGH": "بالا", "MEDIUM": "متوسط", "LOW": "پایین"}.get(
        assessment.confidence, assessment.confidence
    )

    lines = [
        "🟡 گزارش وضعیت بازار طلا",
        f"زمان تولید گزارش: {_time(generated_at)}",
        f"زمان آخرین داده در تحلیل: {_time(assessment.as_of)}",
        "",
        "📊 وضعیت بازار",
        f"• رژیم بازار: {assessment.regime}",
        f"• جهت روند: {trend_fa}",
        f"• شدت نوسان: {volatility_fa}",
        f"• سطح اطمینان تحلیل: {confidence_fa}",
        f"• حمایت تخمینی: {_assessment_value(assessment.support)}",
        f"• مقاومت تخمینی: {_assessment_value(assessment.resistance)}",
        f"• ATR درصدی ۱۴روزه: {_assessment_value(assessment.atr_percent, '%')}",
        "",
        "💹 داده‌های بازار و منابع",
    ]
    if not observations:
        lines.append("• جزئیات قیمت و منبع در این اجرا ارائه نشده است.")
    else:
        for symbol in ("XAUUSD", "DXY", "US10Y", "US02Y", "USOIL", "SPX", "VIX"):
            item = observations.get(symbol)
            if item is None:
                lines.append(f"• {LABEL_FA.get(symbol, symbol)}: در دسترس نیست")
                continue
            lines.append(
                f"• {LABEL_FA.get(symbol, symbol)}: {_price(item.value)} {item.unit} "
                f"| وضعیت: {STATUS_FA.get(item.status, item.status)} "
                f"| منبع: {item.source} | زمان داده: {_time(item.observed_at)}"
            )
            if item.note:
                lines.append(f"  توضیح: {item.note}")

    lines.extend(["", "🌍 زمینه بین‌بازاری"])
    for symbol in ("DXY", "US10Y", "US02Y", "USOIL", "SPX", "VIX"):
        driver = assessment.drivers.get(symbol, "UNKNOWN")
        lines.append(f"• {LABEL_FA.get(symbol, symbol)}: {DRIVER_FA.get(driver, driver)}")
    lines.extend([
        "",
        "🧭 سناریوها",
        f"• سناریوی اصلی: {assessment.main_scenario}",
        f"• سناریوی جایگزین: {assessment.alternative_scenario}",
        "",
        "⚠️ ریسک رویدادها",
    ])
    if assessment.event_risk:
        lines.extend(f"• {event}" for event in assessment.event_risk)
    else:
        lines.append("• رویداد مهمی در ورودی این گزارش ثبت نشده است.")

    lines.extend(["", "🔎 هشدارهای کیفیت داده"])
    if assessment.data_warnings:
        lines.extend(f"• {warning}" for warning in assessment.data_warnings)
    else:
        lines.append("• هشدار مشخصی در اعتبارسنجی داده‌ها ثبت نشده است.")

    lines.extend([
        "",
        "یادآوری: این گزارش تحلیل احتمالی و اطلاعاتی است؛ سیگنال قطعی خرید یا فروش و توصیه مالی نیست.",
        "داده‌های روزانه، تأخیری و زنده ماهیت یکسان ندارند؛ برچسب هر منبع را جداگانه بررسی کنید.",
    ])
    return "\n".join(lines)
