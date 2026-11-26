import unittest
from goldnewsbot.pipeline_preview import extract_text

class ArticleExtractionTests(unittest.TestCase):
    def test_prefers_schema_article_body(self):
        body = 'The Federal Reserve announced a major policy change. ' + ('Detailed market context. ' * 12)
        html = '<html><body><nav>navigation clutter</nav><script type="application/ld+json">' + __import__('json').dumps({'@type':'NewsArticle','articleBody':body}) + '</script><article><p>Visible paragraph is long enough to count but less detailed than schema content.</p></article></body></html>'
        text = extract_text(html)
        self.assertIn('The Federal Reserve announced', text)
        self.assertNotIn('navigation clutter', text)

    def test_extracts_article_paragraphs_not_page_chrome(self):
        long_paragraph = 'Market details and economic context. ' * 12
        html = '<html><header>Header junk</header><main><h1>Headline</h1><p>Central bank policy changed. ' + long_paragraph + '</p></main><aside>Sidebar junk</aside><footer>Footer junk</footer></html>'
        text = extract_text(html)
        self.assertIn('Market details', text)
        self.assertNotIn('Header junk', text)
        self.assertNotIn('Sidebar junk', text)

    def test_short_or_blocked_page_returns_empty(self):
        self.assertEqual(extract_text('<nav>' + 'noise ' * 100 + '</nav>'), '')

    def test_div_text_fallback_when_publisher_has_no_paragraph_tags(self):
        html = '<html><body><nav>menu noise</nav><div>OPEC crude oil supply disruption. ' + ('Detailed article text. ' * 8) + '</div></body></html>'
        text = extract_text(html)
        self.assertIn('OPEC crude oil supply disruption', text)
        self.assertNotIn('menu noise', text)

    def test_preserves_short_partial_publisher_paragraphs(self):
        html = '<article><p>Only the first two paragraphs are currently available.</p><p>Second paragraph with additional verified article details.</p></article>'
        text = extract_text(html, min_chars=1)
        self.assertIn('Only the first two paragraphs', text)
        self.assertIn('additional verified article details', text)

    def test_meta_description_is_fallback(self):
        description = 'Central bank officials discussed interest rates and inflation. ' * 3
        text = extract_text('<meta name="description" content="' + description + '">')
        self.assertIn('Central bank officials', text)

if __name__ == '__main__':
    unittest.main()
