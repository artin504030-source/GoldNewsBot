import argparse
import json
from decimal import Decimal
from market_hours import market_is_closed, weekend_closure_message
from .config import Settings
from .providers import FredProvider, XausSpotProvider, YahooChartProvider
from .history import XausDailyHistoryProvider
from .collector import MarketDataCollector
from .report import render_market_report


def _json_value(value):
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def main():
    parser = argparse.ArgumentParser(description="Gold Market report")
    parser.add_argument(
        "--send-telegram", action="store_true",
        help="send the generated report to the configured Gold Market Telegram chat",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    if args.send_telegram:
        settings.validate_telegram()
        from .delivery import send_telegram_messages
        from .telegram import SIGNATURE_LINES
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        if market_is_closed(now):
            message = weekend_closure_message(now, "Gold Market")
            message += "\n\n" + "\n".join(f"<b>{line}</b>" for line in SIGNATURE_LINES)
            ids = send_telegram_messages(
                settings.telegram_bot_token, settings.telegram_chat_id, (message,)
            )
            print(f"Weekend closure notice delivered: {len(ids)} message(s)")
            return 0

    collector = MarketDataCollector(
        FredProvider(settings.fred_api_key), YahooChartProvider(),
        XausSpotProvider(), XausDailyHistoryProvider()
    )
    assessment, observations, results = collector.collect_report_snapshot()
    report = render_market_report(assessment, observations)
    print(report)

    if args.send_telegram:
        if assessment.trend == "UNAVAILABLE":
            raise SystemExit("Telegram delivery stopped: Gold Market assessment is unavailable")
        from .delivery import send_telegram_messages
        from .telegram import render_telegram_report
        messages = render_telegram_report(assessment, observations)
        message_ids = send_telegram_messages(
            settings.telegram_bot_token, settings.telegram_chat_id, messages
        )
        print(f"Telegram delivery successful: {len(message_ids)} message(s)")

    print("\n--- MACHINE READABLE ASSESSMENT ---")
    keys = (
        "as_of", "regime", "trend", "volatility", "support", "resistance",
        "atr_percent", "drivers", "main_scenario", "alternative_scenario",
        "confidence", "event_risk", "data_warnings",
    )
    print(json.dumps(
        {key: getattr(assessment, key) for key in keys},
        default=_json_value, ensure_ascii=False, indent=2,
    ))
    return 0 if assessment.trend != "UNAVAILABLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
