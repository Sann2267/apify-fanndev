"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-urql -- unlike every other actor in this portfolio, the JSON-LD block
             on theatlantic.com is metadata-only (no `articleBody`). Full
             text lives in an Apollo/urql GraphQL client cache embedded in
             `__NEXT_DATA__` (`props.pageProps.urqlState`), as a list of
             `ArticleParagraphContent`/image/embed blocks under
             `article.content`. This picks the cache entry that actually
             carries `content`, concatenates paragraph blocks' `innerHtml`,
             and strips HTML tags for a plain-text `articleBody` (mirroring
             the shape every other actor in this portfolio emits) while also
             passing through the raw `content` block list for consumers who
             want the structured/HTML form.
  S2-atom -- the "best of" feed is **Atom**, not RSS 2.0 (`<feed>/<entry>`,
             `<link rel="alternate">`, `<summary>`, `<published>`/
             `<updated>`, possibly multiple `<author>` tags for co-bylines).
             Notably the feed's own `<content type="html">` already carries
             the full article body -- not used here, kept teaser-only
             (`summary`) for consistency with every other actor's `latest`
             mode in this portfolio; use `article` mode for full text.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S | re.I
)
TAG_RE = re.compile(r"<[^<]+?>")


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _strip_html(html: str) -> str:
    return TAG_RE.sub("", html or "")


def _find_article_cache(urql_state: dict) -> dict | None:
    for entry in urql_state.values():
        raw = entry.get("data") if isinstance(entry, dict) else None
        if not raw:
            continue
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            continue
        article = parsed.get("article") if isinstance(parsed, dict) else None
        if isinstance(article, dict) and article.get("content"):
            return article
    return None


def extract_article(html: str, url: str) -> dict:
    match = NEXT_DATA_RE.search(html)
    if not match:
        raise UnexpectedShape("No __NEXT_DATA__ script found -- page shape has likely changed.")
    try:
        next_data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        raise UnexpectedShape(f"__NEXT_DATA__ is not valid JSON: {e!r}")

    urql_state = next_data.get("props", {}).get("pageProps", {}).get("urqlState")
    if not urql_state:
        raise UnexpectedShape("No urqlState in __NEXT_DATA__ -- page shape has likely changed.")

    article = _find_article_cache(urql_state)
    if not article:
        raise UnexpectedShape(
            "No cached article with 'content' found in urqlState -- page shape has likely changed."
        )

    content_blocks = article.get("content") or []
    paragraphs = [
        _strip_html(b.get("innerHtml", ""))
        for b in content_blocks
        if isinstance(b, dict) and b.get("__typename") == "ArticleParagraphContent"
    ]
    article_body = "".join(paragraphs)
    if not article_body:
        raise UnexpectedShape("Found article cache but extracted 0 paragraph blocks.")

    authors = [
        {"name": a.get("displayName"), "url": a.get("url")}
        for a in (article.get("authors") or [])
        if isinstance(a, dict)
    ]
    tags = [t.get("name") for t in (article.get("tags") or []) if isinstance(t, dict) and t.get("name")]

    return {
        "_input": url,
        "_source": "S1-urql",
        "_scrapedAt": utc_now_iso(),
        "headline": article.get("title"),
        "description": article.get("dek"),
        "articleBody": article_body,
        "url": article.get("canonicalUrl") or article.get("url") or url,
        "author": authors,
        "tags": tags,
        "hasMeter": article.get("hasMeter"),
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "primaryCategory": (article.get("primaryCategory") or {}).get("displayName"),
        "contentBlockCount": len(content_blocks),
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_rss_items(xml_bytes: bytes) -> list[dict]:
    """Parse The Atlantic's Atom feed (`<feed>/<entry>`), not RSS 2.0."""
    soup = BeautifulSoup(xml_bytes, "xml")
    items = []
    for entry in soup.find_all("entry"):
        title = entry.find("title")
        link_tag = entry.find("link", rel="alternate") or entry.find("link")
        entry_id = entry.find("id")
        published = entry.find("published")
        updated = entry.find("updated")
        summary = entry.find("summary")
        authors = [
            a.find("name").text.strip()
            for a in entry.find_all("author")
            if a.find("name") and a.find("name").text
        ]
        items.append(
            {
                "_input": "latest",
                "_source": "S2-atom",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title else None,
                "link": link_tag.get("href").strip() if link_tag and link_tag.get("href") else None,
                "guid": entry_id.text.strip() if entry_id else None,
                "pubDate": published.text.strip() if published else None,
                "updated": updated.text.strip() if updated else None,
                "description": summary.text.strip() if summary else None,
                "authors": authors,
            }
        )
    return items
