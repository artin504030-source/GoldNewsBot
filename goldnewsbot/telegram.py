import requests

class TelegramSender:
    def __init__(self, token: str, chat_id: str, parse_mode: str = "HTML", timeout: int = 15):
        if not token or not chat_id:
            raise ValueError("Telegram credentials are not configured")
        self._token = token
        self._chat_id = chat_id
        self._parse_mode = parse_mode
        self._timeout = timeout

    def send(self, text: str) -> None:
        if not text.strip():
            raise ValueError("Telegram message cannot be empty")
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        response = requests.post(
            url,
            json={"chat_id": self._chat_id, "text": text, "parse_mode": self._parse_mode,
                  "disable_web_page_preview": True},
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError("Telegram API rejected the message")
