"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-flight -- dnaindia.com is a Next.js App Router (React Server Components)
               site. There is NO `<script type="application/ld+json">` tag
               and NO `__NEXT_DATA__` blob anywhere in the SSR HTML -- both
               of this portfolio's usual first-choice anchors are absent.
               Instead, the article's structured data is embedded inside a
               React Server Components "flight" stream: many
               `<script>self.__next_f.push([1,"..."])</script>` tags
               scattered through the page, where the second array element is
               itself a JSON-encoded STRING (the flight text is escaped one
               level deeper than ordinary inline JSON). Unlike simpler
               flight-payload sites already in this portfolio (see
               star-kenya-scraper), a single logical "row" can be SPLIT
               across multiple separate push() calls with no repeated id
               prefix on the continuation fragments, and the resolved
               NewsArticle-equivalent object references its own
               `articleBody` via a cross-chunk pointer (`"$12"`) into a
               *separate* numbered row elsewhere in the stream, rather than
               carrying the body text inline. `_build_flight_stream()`
               concatenates every push() payload in document order into one
               continuous string first (which transparently repairs the
               split-row issue), then `_find_newsarticle()` locates the
               `"newsarticle":{...}` key (a fully-RESOLVED copy of the
               NewsArticle node -- author/image/publisher/mainEntityOfPage
               already inlined, no ref resolution needed for those) via a
               balanced-brace walk, and `_resolve_text_ref()` follows the
               remaining `"$<hex_id>"` pointer for `articleBody` to its own
               `<hex_id>:T<hex_length>,<raw text>` row elsewhere in the
               stream. See skills/balanced-brace-json.md for the walker
               pattern this builds on.
  S2-sitemap -- Google News sitemap (`/googlenews.xml`, referenced from
               robots.txt) for `latest` mode. `news:title` / `news:
               publication_date` / `news:keywords` per entry -- no RSS feed
               needed, this already carries a real title and per-article
               timestamp.

Not-found: nonexistent article slugs return a REAL HTTP 404 (confirmed on a
deliberately-invented slug) -- no soft-404 quirk observed.
"""

import html as html_module
import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

NEWSARTICLE_ANCHOR = '"newsarticle":{"@context":"https://schema.org","@type":"NewsArticle"'


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_balanced(text: str, start: int, open_ch: str, close_ch: str) -> str | None:
    """Balanced open/close-char walker that tracks JSON string quoting so
    braces/brackets inside string values don't throw off the depth count.
    See skills/balanced-brace-json.md."""
    if start >= len(text) or text[start] != open_ch:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    return None  # truncated / unbalanced


def _build_flight_stream(html_text: str) -> str:
    """Concatenate every `self.__next_f.push([1,"..."])` payload string, in
    document order, into one continuous text stream. A single flight "row"
    is sometimes split across multiple push() calls (a long module-dependency
    list, or a long text/body chunk) -- only the first fragment of a row
    carries the `<hex_id>:` prefix, later fragments are raw continuation text
    with no prefix of their own. Simple in-order concatenation reassembles
    split rows correctly without needing to detect "new row" vs
    "continuation" explicitly."""
    parts = []
    for m in re.finditer(r"self\.__next_f\.push\(", html_text):
        start = html_text.find("[", m.end())
        if start == -1:
            continue
        blob = _extract_balanced(html_text, start, "[", "]")
        if blob is None:
            continue
        try:
            arr = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if isinstance(arr, list) and len(arr) >= 2 and isinstance(arr[1], str):
            parts.append(arr[1])
    return "".join(parts)


def _find_newsarticle(stream: str) -> dict | None:
    """Locate the fully-resolved `"newsarticle":{...}` object embedded in the
    flight stream's `schema` prop. A *second*, less-resolved copy of the same
    data also exists elsewhere in the stream under a bare numbered chunk, with
    several fields (image, author, publisher, mainEntityOfPage) replaced by
    `"$<id>"` cross-chunk references -- the `"newsarticle":` key is used
    instead specifically because everything except `articleBody` is already
    inline there."""
    idx = stream.find(NEWSARTICLE_ANCHOR)
    if idx == -1:
        return None
    brace_start = stream.find("{", idx + len('"newsarticle":'))
    blob = _extract_balanced(stream, brace_start, "{", "}")
    if blob is None:
        return None
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return None


def _resolve_text_ref(stream: str, ref) -> str | None:
    """Resolve a `"$<hex_id>"` cross-chunk reference to its React Flight text
    row (`<hex_id>:T<hex_length>,<raw text>`). `articleBody` on this CMS is
    always such a reference, never an inline string."""
    if not isinstance(ref, str) or not ref.startswith("$"):
        return ref
    chunk_id = ref[1:]
    m = re.search(rf"(?:^|\n){re.escape(chunk_id)}:T([0-9a-f]+),", stream)
    if not m:
        return None
    length = int(m.group(1), 16)
    return stream[m.end() : m.end() + length]


def _unescape_deep(value):
    """Recursively html.unescape() every string value. This CMS's flight
    payload carries text that is HTML-entity-encoded a second time on top of
    the JSON encoding (e.g. headline containing literal `&#039;`/`&quot;`
    instead of a real apostrophe/quote character) -- applied everywhere for
    robustness, a no-op wherever there's nothing to unescape."""
    if isinstance(value, str):
        return html_module.unescape(value)
    if isinstance(value, dict):
        return {k: _unescape_deep(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_unescape_deep(v) for v in value]
    return value


def extract_article(html_text: str, url: str) -> dict:
    stream = _build_flight_stream(html_text)
    news_article = _find_newsarticle(stream)
    if news_article is None:
        raise UnexpectedShape(
            "No newsarticle flight payload found -- page shape has likely changed."
        )

    news_article = _unescape_deep(news_article)
    article_body = _resolve_text_ref(stream, news_article.get("articleBody"))
    if article_body is not None:
        article_body = html_module.unescape(article_body)

    return {
        "_input": url,
        "_source": "S1-flight",
        "_scrapedAt": utc_now_iso(),
        **{k: v for k, v in news_article.items() if k != "articleBody"},
        "articleBody": article_body,
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_sitemap_items(xml_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    url_nodes = soup.find_all("url")
    if not url_nodes:
        raise UnexpectedShape(
            "No <url> elements found in Google News sitemap -- feed shape has likely changed."
        )

    results = []
    for url_node in url_nodes:
        loc = url_node.find("loc")
        link = loc.text.strip() if loc and loc.text else None
        if not link:
            continue
        title_tag = url_node.find("news:title")
        pubdate_tag = url_node.find("news:publication_date")
        keywords_tag = url_node.find("news:keywords")
        results.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": html_module.unescape(title_tag.text.strip())
                if title_tag and title_tag.text
                else None,
                "link": link,
                "publication_date": pubdate_tag.text.strip()
                if pubdate_tag and pubdate_tag.text
                else None,
                "keywords": keywords_tag.text.strip() if keywords_tag and keywords_tag.text else None,
            }
        )

    # Observed already newest-first in file order during recon, but sorted
    # descending by publication_date defensively -- not guaranteed on every
    # fetch.
    results.sort(key=lambda r: r["publication_date"] or "", reverse=True)
    return results
