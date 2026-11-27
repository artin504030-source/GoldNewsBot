import unittest
from daily_digest import split_message


class DailyDigestSplitTests(unittest.TestCase):
    def test_keeps_short_message_as_single_chunk(self):
        self.assertEqual(split_message("line one\\nline two"), ["line one\\nline two"])

    def test_splits_long_message_without_exceeding_limit(self):
        message = "\\n".join(["x" * 1000 for _ in range(10)])
        chunks = split_message(message, limit=2500)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 2500 for chunk in chunks))
        self.assertEqual("".join(chunks).replace("x", ""), "")

    def test_splits_single_oversized_line(self):
        chunks = split_message("a" * 5000, limit=2000)
        self.assertEqual([len(chunk) for chunk in chunks], [2000, 2000, 1000])


if __name__ == "__main__":
    unittest.main()
