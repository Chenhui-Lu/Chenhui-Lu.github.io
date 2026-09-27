#!/usr/bin/env python3
"""Validate the public landing page before deployment."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
INDEX = PUBLIC / "index.html"


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self.links: list[str] = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_entityref(self, name: str) -> None:
        if self._in_title:
            self.title += f"&{name};"

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # type: ignore[no-redef]
        values = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> int:
    required = [INDEX, PUBLIC / "styles.css", PUBLIC / ".nojekyll"]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        fail(f"Missing public files: {', '.join(missing)}")

    html = INDEX.read_text(encoding="utf-8")
    parser = PageParser()
    parser.feed(html)

    if "Chenhui Lu" not in html or "Research Progress Portal" not in html:
        fail("Required public identity text is missing")
    if "View Research Progress" not in html:
        fail("Primary dashboard link label is missing")
    if not any(link.startswith("https://") and "pages.dev" in link for link in parser.links):
        fail("The protected Cloudflare Pages link is missing")

    forbidden_public_terms = [
        "recent progress",
        "current work",
        "current priorities",
        "index cartel",
        "amazon data",
    ]
    lowered = html.lower()
    leaked = [term for term in forbidden_public_terms if term in lowered]
    if leaked:
        fail(f"Potential research details found in public page: {', '.join(leaked)}")

    credential_patterns = [
        r"ghp_[A-Za-z0-9]{20,}",
        r"github_pat_[A-Za-z0-9_]{20,}",
        r"(?:api[_-]?key|client[_-]?secret|password)\s*[:=]\s*['\"][^'\"]+",
    ]
    for path in PUBLIC.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in credential_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                fail(f"Potential credential found in {path.relative_to(ROOT)}")

    print("Public landing validation passed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, OSError) as error:
        print(f"Validation failed: {error}", file=sys.stderr)
        sys.exit(1)
