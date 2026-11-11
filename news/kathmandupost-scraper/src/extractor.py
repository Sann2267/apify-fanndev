"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html  -- kathmandupost.com emits only 2 ld+json blocks per article
              page: an `Organization` block and the `NewsArticle` itself
              -- the extractor scans all blocks and picks the one whose
              `@type` is `NewsArticle`. That block carries `headline`,
              `image`, `publisher`, and `description` -- but **no
              `articleBody`**, **no `datePublished`/`dateModified`**, and
              **no `author`** (unlike most portfolio targets, this site's
              ld+json is unusually thin). Full text, byline, and dates
              all come from HTML instead:
                - Body: `section.story-section` -- direct-child `<p>`
                  tags only. Confirmed clean (no ad/related-post/embed
                  markup mixed in as direct children) on 7 sampled
                  articles across national/world/money/sports/opinion/
                  editorial/columns/visual-stories sections.
                - Byline: `<a href="/author/<slug>">Name</a>` tags --
                  collected and de-duplicated (the same link appears once
                  near the top of the page and again in the bottom
                  `div.author-info` bio block). Absent entirely on
                  editorial/unsigned pieces -- treated as optional, not
                  raised on.
                - Dates: `div.updated-time` blocks with plain-text
                  `"Published at : <date>"` / `"Updated at : <date>"` --
                  passed through as raw upstream strings (no machine-
                  parseable ISO date is available anywhere on the page,
                  so there is nothing cleaner to normalize to). A third
                  `div.updated-time.updated-time_location` carries just a
                  city name (e.g. "Kathmandu").
                - Category: not carried by ld+json (no BreadcrumbList
                  block exists on this site) -- taken from the first path
                  segment of the article URL itself (e.g. `/national/...`
                  -> `"national"`), which is stable and always present
                  since it's part of the URL scheme.
  Soft-404 -- a nonexistent article slug returns HTTP 200 rendering the
              homepage shell (generic `<title>` = "The Kathmandu Post |
              Read online latest news and articles from Nepal", no
              `NewsArticle` ld+json block, no `section.story-section`),
              not a distinct error page or a real 404 status. Detected by
              requiring BOTH signals of a real article to be absent AND
              the title to match the generic homepage title.
  S2-rss   -- `/rss` (NOT `/feed`, `/rss.xml`, or any of the sitemap.xml
              variants -- all of those soft-404 to the homepage shell,
              see CRAWLING_METHOD.md). A minimal RSS 2.0 feed with only
              `title`/`link`/`description` per `<item>` -- no `pubDate`,
              `guid`, `category`, or `enclosure`. ~40 items, newest first,
              spanning roughly the last 2 days at sample time.
"""

import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.constants import GENERIC_TITLE


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


class SoftNotFound(Exception):
    """Page returned HTTP 200 but is actually the soft-404 homepage shell."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_news_article(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("@type") == "NewsArticle":
            return data
    return None


def is_soft_404(soup: BeautifulSoup) -> bool:
    has_news_article = _find_news_article(soup) is not None
    has_story_section = soup.select_one("section.story-section") is not None
    if has_news_article or has_story_section:
        return False
    title_tag = soup.find("title")
    title_text = title_tag.get_text(strip=True) if title_tag else ""
    return title_text == GENERIC_TITLE


def _extract_body(soup: BeautifulSoup) -> str:
    container = soup.select_one("section.story-section")
    if container is None:
        raise UnexpectedShape("No section.story-section element found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p", recursive=False)]
    paragraphs = [p for p in paragraphs if p]
    return "\n\n".join(paragraphs)


def _extract_authors(soup: BeautifulSoup) -> list[str]:
    seen: list[str] = []
    for a in soup.select('a[href^="/author/"]'):
        name = a.get_text(strip=True)
        if name and name not in seen:
            seen.append(name)
    return seen


def _extract_meta(soup: BeautifulSoup) -> tuple[str | None, str | None, str | None]:
    published, updated, location = None, None, None
    for div in soup.select("div.updated-time"):
        text = div.get_text(" ", strip=True)
        if text.startswith("Published at"):
            published = text.split(":", 1)[1].strip() if ":" in text else text
        elif text.startswith("Updated at"):
            updated = text.split(":", 1)[1].strip() if ":" in text else text
        elif text:
            location = text
    return published, updated, location


def _extract_category(url: str) -> str | None:
    path = urlparse(url).path.strip("/")
    segments = path.split("/") if path else []
    return segments[0] if segments and segments[0] else None


def extract_article(html_text: str, url: str) -> dict:
    # NOTE: "html.parser" (stdlib), NOT "lxml" -- on this site lxml's HTML
    # tokenizer silently drops 2 of 26 <script> tags on every sampled
    # article page, including the one and only <script type=
    # "application/ld+json"> block that carries @type=NewsArticle (the
    # sibling Organization block survives, so the shape looked plausible
    # at first -- only counting script tags exposed it). Confirmed via
    # `html.count("<script")` (26) vs BeautifulSoup(html, "lxml") finding
    # only 24 <script> tags, vs "html.parser" correctly finding all 26.
    # See CRAWLING_METHOD.md.
    soup = BeautifulSoup(html_text, "html.parser")

    if is_soft_404(soup):
        raise SoftNotFound("No NewsArticle block and no story-section -- generic homepage title returned.")

    article_body = _extract_body(soup)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    news_article = _find_news_article(soup)
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    publisher = news_article.get("publisher") or {}
    authors = _extract_authors(soup)
    published_at, updated_at, location = _extract_meta(soup)

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "headline": news_article.get("headline"),
        "description": news_article.get("description"),
        "articleBody": article_body,
        "author": ", ".join(authors) if authors else None,
        "publisher": publisher.get("name") if isinstance(publisher, dict) else publisher,
        "category": _extract_category(url),
        "publishedAt": published_at,
        "updatedAt": updated_at,
        "location": location,
        "image": news_article.get("image"),
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


_CDATA_STRIP_RE = re.compile(r"^<!\[CDATA\[(.*)\]\]>$", re.S)


def _rss_text(tag) -> str | None:
    if tag is None or not tag.text:
        return None
    text = tag.text.strip()
    m = _CDATA_STRIP_RE.match(text)
    return (m.group(1).strip() if m else text) or None


def extract_rss_items(xml_text: str) -> list[dict]:
    # A `<script>` beacon tag is appended by Cloudflare after the closing
    # `</rss>` root element -- technically invalid XML, but lxml's XML
    # parser (via BeautifulSoup) tolerates trailing garbage after the root
    # closes and still parses every <item> correctly (confirmed: 40/40
    # items parsed on a sampled feed).
    soup = BeautifulSoup(xml_text, "xml")
    items = soup.find_all("item")
    if not items:
        raise UnexpectedShape("No <item> elements found in RSS feed -- feed shape has likely changed.")
    results = []
    for item in items:
        title = item.find("title")
        link = item.find("link")
        description = item.find("description")
        results.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": _rss_text(title),
                "link": _rss_text(link),
                "description": _rss_text(description),
            }
        )
    return results
