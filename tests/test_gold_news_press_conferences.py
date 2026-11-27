import unittest
from apps.gold_news_press_conferences.__main__ import is_conference_candidate, get_event_image

class PressConferenceTests(unittest.TestCase):
    def test_detects_central_bank_press_conference(self):
        self.assertTrue(is_conference_candidate(
            "ECB press conference following monetary policy decision",
            "Transcript and questions and answers"
        ))

    def test_detects_fed_transcript(self):
        self.assertTrue(is_conference_candidate(
            "Federal Reserve transcript of press conference",
            "Remarks and Q&A"
        ))

    def test_rejects_unrelated_company_conference(self):
        self.assertFalse(is_conference_candidate(
            "Technology company press conference",
            "New product launch"
        ))

    def test_uses_image_from_specific_publisher_page(self):
        html = '<meta property="og:image" content="/images/ecb-conference.jpg">'
        self.assertEqual(
            get_event_image({}, html, "https://www.ecb.europa.eu/press/"),
            "https://www.ecb.europa.eu/images/ecb-conference.jpg"
        )

    def test_rejects_non_https_or_empty_image(self):
        self.assertEqual(get_event_image({}, '<meta property="og:image" content="http://bad.example/a.jpg">', "https://example.com"), "")

if __name__ == "__main__":
    unittest.main()
