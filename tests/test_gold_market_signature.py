import unittest

from apps.gold_market.telegram import _telegram_lines


class GoldMarketSignatureTests(unittest.TestCase):
    def test_signature_is_appended_as_two_bold_lines(self):
        self.assertEqual(
            _telegram_lines("Gold market report"),
            [
                "<b>Gold Channel | XAU</b>",
                "",
                "<b>عنوان:</b>",
                "Gold market report",
                "",
                "<b>متن:</b>",
                "",
                "<b>Gold Admin</b>",
                "<b>Market Admin</b>",
            ],
        )


if __name__ == "__main__":
    unittest.main()
