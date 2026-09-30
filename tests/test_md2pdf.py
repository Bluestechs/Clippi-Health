"""Semantic Markdown and interactive-link safety; synthetic documents only."""
from html.parser import HTMLParser
import unittest

from scripts.md2pdf import md_to_html


class Structure(HTMLParser):
    def __init__(self, document):
        super().__init__()
        self.elements = []
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class MarkdownTests(unittest.TestCase):
    def test_checklist_has_semantic_formatting(self):
        document = md_to_html(
            "# Registration\n\n## Settings\n\n- **Public client**\n- *Your identity*\n\n"
            "1. Register `http://127.0.0.1:8765/oauth/callback`.\n2. Save your ID.\n",
            render_links=True,
        )
        tags = {tag for tag, _ in Structure(document).elements}
        self.assertTrue({"h1", "h2", "ul", "ol", "strong", "em", "code"}.issubset(tags))
        self.assertNotIn("pre", tags)

    def test_interactive_links_escape_attributes_and_reject_active_schemes(self):
        markdown = (
            '[Official](https://example.test/?value="quoted"&next=1)\n\n'
            '[Unsafe](javascript:alert)\n\n'
            '<script>alert("unsafe")</script>\n'
        )
        elements = Structure(md_to_html(markdown, render_links=True)).elements
        self.assertEqual([attrs for tag, attrs in elements if tag == "a"],
                         [{"href": 'https://example.test/?value="quoted"&next=1'}])
        self.assertNotIn("script", {tag for tag, _ in elements})
        printable = Structure(md_to_html(markdown, render_links=False)).elements
        self.assertNotIn("a", {tag for tag, _ in printable})


if __name__ == "__main__":
    unittest.main()
