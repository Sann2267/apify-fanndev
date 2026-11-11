"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld       -- omanobserver.om emits exactly ONE ld+json block per
                     article page, typed `NewsArticle`, and it **includes
                     `articleBody` directly** (full text, verified
                     641-2754 bytes across 5 sampled articles spanning
                     news/oman, business, sports, and a podcast-episode
                     page -- no truncation, no "..." markers, no
                     `isAccessibleForFree` field or any other paywall
                     marker on any sample). No HTML fallback needed --
                     the extractor still scans all ld+json blocks (not
                     just the first) and picks the one whose `@type` is
                     `NewsArticle`, for robustness against a future
                     template that adds more blocks (e.g. Organization,
                     BreadcrumbList). `author` is a single `Person`
                     object (not a list, unlike Gulf News/Kyiv Post) --
                     every sample used the generic byline "Observer Web
                     Team" or a named reporter. `publisher` and
                     `copyrightHolder` are both `Organization` nodes
                     (same name, "Oman Observer", on every sample).
                     **Quirk:** `keywords` contains literal un-decoded
                     HTML entities (`&#039;` confirmed for an apostrophe
                     in "South Korea's Doosan..." -> keywords string
                     "South,Korea&#039;s,Doosan,..."). This is a CMS quirk
                     that embeds the entity directly into the JSON string
                     value (not a JSON-escaping issue -- `json.loads`
                     already handles those) -- `html.unescape()` is
                     applied to `headline`/`description`/`articleBody`/
                     `keywords` defensively, matching the same quirk
                     documented for gulfnews-scraper. Note `keywords` is
                     just the headline's words comma-joined by the CMS
                     (auto-generated SEO tags, not curated topic tags) --
                     passed through as-is per raw-passthrough convention.
                     `url` in the ld+json block is the article's TRUE
                     canonical URL regardless of what category/slug
                     segments were requested -- confirmed by requesting
                     the same numeric article ID with a deliberately
                     wrong category and slug and getting back identical
                     content with the correct canonical `url` value. The
                     numeric ID is the only part of the path the server
                     actually uses for routing.
  S2-html-listing -- no working RSS/sitemap exists (`/feed` = 404, every
                     `sitemap*.xml`/`rss.xml` variant probed = 404, and
                     `/rss` itself returns HTTP 200 but is a soft page,
                     not a feed -- see constants.py docstring). The
                     homepage is scraped instead for `<a href>` links
                     matching `/article/<id>/...`, same fallback pattern
                     as chinadaily-scraper. The numeric article ID is a
                     plain auto-increment primary key (not date-encoded
                     like chinadaily's hex ID or jamaicagleaner's
                     YYYYMMDD path segment), but recon confirmed it
                     correlates monotonically with `datePublished`
                     (spot-checked 4 IDs spanning Aug 19-25 2026 --
                     strictly increasing ID = strictly increasing
                     publish time) -- so sorting descending by numeric
                     ID reproduces newest-first order without visiting
                     each article. **Quirk:** the homepage's "hero card"
                     widgets wrap BOTH the headline (`div.title`) AND a
                     teaser paragraph (`div.description`) inside the
                     same `<a>` -- naively taking `a.get_text()` glues
                     the two together into one run-on string. Every
                     single article-link anchor on the homepage (105/105
                     occurrences checked) carries a clean `title="..."`
                     attribute holding exactly the headline with no
                     teaser text, so the extractor reads `a["title"]`
                     first and only falls back to `a.get_text()` if an
                     anchor has no `title` attribute at all.
"""

import html
import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

ARTICLE_URL_RE = re.compile(r"/article/(\d+)(/[^\"'#?]*)?")


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


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


def _unescape(value):
    return html.unescape(value) if isinstance(value, str) else value


def _org_name(node):
    if isinstance(node, dict):
        return node.get("name")
    return node


def _url_category_path(url: str) -> list[str] | None:
    """Best-effort category/subcategory segments from the URL path.

    Not raised on if the URL doesn't match -- purely a nice-to-have
    derived from the path, since the site itself doesn't emit an
    `articleSection`/breadcrumb field in ld+json.
    """
    m = re.search(r"/article/\d+/([^?#]*)", url)
    if not m or not m.group(1):
        return None
    segments = [s for s in m.group(1).split("/") if s]
    return segments[:-1] if len(segments) > 1 else None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article = _find_news_article(soup)
    if article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    article_body = article.get("articleBody")
    if not article_body:
        raise UnexpectedShape("articleBody missing from NewsArticle node -- page shape has likely changed.")
    article_body = _unescape(article_body)

    return {
        "_input": url,
        "_source": "S1-jsonld",
        "_scrapedAt": utc_now_iso(),
        "headline": _unescape(article.get("headline")),
        "description": _unescape(article.get("description")),
        "articleBody": article_body,
        "keywords": _unescape(article.get("keywords")),
        "author": _org_name(article.get("author")),
        "publisher": _org_name(article.get("publisher")),
        "copyrightHolder": _org_name(article.get("copyrightHolder")),
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "dateCreated": article.get("dateCreated"),
        "image": article.get("image"),
        "thumbnailUrl": article.get("thumbnailUrl"),
        "inLanguage": article.get("inLanguage"),
        "url": article.get("url"),
        "urlCategoryPath": _url_category_path(url),
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def _normalize_url(href: str) -> str:
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return "https://www.omanobserver.om" + href
    return href


def extract_latest_items(html_text: str) -> list[dict]:
    soup = BeautifulSoup(html_text, "lxml")

    titles: dict[str, str] = {}
    links: dict[str, str] = {}
    order: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = ARTICLE_URL_RE.search(href)
        if not m:
            continue
        article_id = m.group(1)
        # Prefer the anchor's `title` attribute -- it's the clean headline.
        # a.get_text() on "hero card" anchors glues the headline together
        # with a teaser paragraph nested in the same <a> (see docstring).
        text = (a.get("title") or "").strip() or a.get_text(strip=True)
        if article_id not in titles:
            order.append(article_id)
            titles[article_id] = ""
            links[article_id] = _normalize_url(href)
        if text and len(text) > len(titles[article_id]):
            titles[article_id] = text

    if not order:
        raise UnexpectedShape("No /article/<id>/... links found on homepage -- page shape has likely changed.")

    order.sort(key=lambda i: int(i), reverse=True)

    items = []
    for article_id in order:
        link = links[article_id]
        items.append(
            {
                "_input": "latest",
                "_source": "S2-html-listing",
                "_scrapedAt": utc_now_iso(),
                "title": titles[article_id] or None,
                "link": link,
                "articleId": int(article_id),
                "urlCategoryPath": _url_category_path(link),
            }
        )
    return items
