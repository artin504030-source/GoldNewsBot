import json
import unittest
from unittest.mock import patch, Mock

from apps.gold_market.delivery import (
    TelegramDeliveryError,
    send_telegram_messages,
)


class TelegramDeliveryTests(unittest.TestCase):
    @patch("apps.gold_market.delivery.urlopen")
    def test_sends_html_and_returns_message_ids(self, mocked_urlopen):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps({
            "ok": True, "result": {"message_id": 123}
        }).encode()
        mocked_urlopen.return_value = response

        ids = send_telegram_messages("token", "-100123", ("<b>Gold</b>",))

        self.assertEqual(ids, (123,))
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.method, "POST")
        payload = json.loads(request.data.decode())
        self.assertEqual(payload["chat_id"], "-100123")
        self.assertEqual(payload["parse_mode"], "HTML")
        self.assertEqual(payload["text"], "<b>Gold</b>")

    @patch("apps.gold_market.delivery.urlopen")
    def test_telegram_rejection_is_reported(self, mocked_urlopen):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps({
            "ok": False, "description": "Forbidden"
        }).encode()
        mocked_urlopen.return_value = response

        with self.assertRaisesRegex(TelegramDeliveryError, "Forbidden"):
            send_telegram_messages("token", "-100123", ("hello",))

    def test_requires_credentials_and_message(self):
        with self.assertRaises(ValueError):
            send_telegram_messages("", "-100123", ("hello",))
        with self.assertRaises(ValueError):
            send_telegram_messages("token", "-100123", ())


if __name__ == "__main__":
    unittest.main()
