"""Telegram delivery client for Gold Market reports."""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class TelegramDeliveryError(RuntimeError):
    """Raised when Telegram rejects or cannot receive a report."""


def send_telegram_messages(
    bot_token: str,
    chat_id: str,
    messages: tuple[str, ...],
    timeout: int = 20,
) -> tuple[int, ...]:
    """Send HTML messages sequentially and return Telegram message IDs."""
    if not bot_token or not chat_id:
        raise ValueError("Telegram bot token and chat ID are required")
    if not messages:
        raise ValueError("At least one Telegram message is required")

    endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    sent_ids: list[int] = []
    for index, message in enumerate(messages, start=1):
        payload = json.dumps({
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }).encode("utf-8")
        request = Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise TelegramDeliveryError(
                f"Telegram request failed on message {index}: {type(exc).__name__}"
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TelegramDeliveryError(
                f"Telegram returned an invalid response on message {index}"
            ) from exc

        if not isinstance(result, dict) or result.get("ok") is not True:
            description = result.get("description", "unknown Telegram error") if isinstance(result, dict) else "invalid Telegram response"
            raise TelegramDeliveryError(f"Telegram rejected message {index}: {description}")
        message_id = result.get("result", {}).get("message_id")
        if not isinstance(message_id, int):
            raise TelegramDeliveryError(f"Telegram response omitted message_id for message {index}")
        sent_ids.append(message_id)
    return tuple(sent_ids)
