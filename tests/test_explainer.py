"""Checks on docs/index.html: self-contained, small, in sync with the fixtures."""
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "docs", "index.html")


def page():
    with open(PAGE, "r", encoding="utf-8") as fh:
        return fh.read()


class ExplainerTests(unittest.TestCase):
    def test_single_file_no_network_under_150kb(self):
        html = page()
        self.assertLess(len(html.encode("utf-8")), 150 * 1024)
        self.assertNotRegex(html, r"https?://")
        self.assertNotRegex(html, r"<script[^>]+src=")
        self.assertIn('<meta name="color-scheme" content="light dark">', html)

    def test_rail_anchors_resolve_and_match_headings(self):
        html = page()
        nav = re.search(r"<nav.*?</nav>", html, re.S).group(0)
        links = re.findall(r'<a href="#([^"]+)"[^>]*>([^<]+)</a>', nav)
        self.assertEqual(len(links), 4)
        for target, label in links:
            heading = re.search(r'<section id="{}"[^>]*>\s*<h[12]>([^<]+)</h[12]>'.format(target), html)
            self.assertIsNotNone(heading, target)
            self.assertEqual(heading.group(1), label)

    def test_embedded_data_is_current(self):
        done = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_explainer_data.py"),
                               "--check"])
        self.assertEqual(done.returncode, 0, "run tools/make_explainer_data.py")


if __name__ == "__main__":
    unittest.main()
