"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html          -- guardian.co.tt emits exactly 1 ld+json block per
                      article page, typed `NewsArticle`, with `headline`,
                      `description`, `dateModified`, `isAccessibleForFree`
                      (emitted as the *string* "true"/"false", not a JSON
                      boolean), and `image` -- but no `articleBody`, no
                      `author`, no `datePublished`, and no `publisher`.
                      Full text comes from HTML: `div.ag-article-text`
                      contains a mix of `<p class="bodytext">`,
                      `<p class="byline">` (a reporter signature block
                      some -- not all -- writers prepend to their own
                      copy), and interleaved `<p class="Caption">` /
                      `<p class="Source">` paragraphs that belong to inline
                      images, not the article prose. Only `bodytext`/
                      `byline` paragraphs are joined into `articleBody`;
                      `Caption`/`Source` are explicitly excluded. `author`
                      is pulled separately from the article header's
                      `div.author > span` (present for staff bylines and
                      desk credits like "Sport Desk"; absent/empty on wire
                      pieces and some opinion columns -- treated as
                      optional, not raised on). `datePublished` is not in
                      ld+json at all -- it's synthesized from the header's
                      `span.textelement-createdtime` (`YYYYMMDDHHMMSS`),
                      assuming Trinidad & Tobago's fixed UTC-4 offset (AST,
                      no DST observed) -- the raw string is kept alongside
                      as `createdTimeRaw` for anyone who wants to verify or
                      re-derive it. `span.textelement-publishing.date`
                      (`YYYYMMDD`, day precision) is kept as a secondary/
                      redundant `publishDateRaw` field. `category` is
                      parsed from the URL path's first segment (e.g.
                      "news", "business", "sports", "opinion", "article")
                      since there is no BreadcrumbList block to pull it
                      from. Upstream also injects U+00AD SOFT HYPHEN
                      characters mid-word throughout body/description text
                      (an invisible line-break-hinting artifact from the
                      CMS's justified-text renderer, e.g. "Cham­ber"
                      for "Chamber") -- stripped from every text field
                      since it carries no semantic content and would
                      otherwise litter the dataset with invisible
                      characters mid-word.
  S2-html-listing  -- the site has no RSS feed and no sitemap.xml at all
                      (not merely broken -- every path probed 404s, and
                      the homepage HTML has zero mentions of "rss",
                      "sitemap", or "feed"). Instead the homepage is
                      scraped for `<a href>` links matching
                      `/<section>/<slug>-6.2.<id>.<hash>`. Unlike Jamaica
                      Gleaner, there's no date embedded in the URL -- the
                      numeric CMS content `<id>` (auto-increment) is used
                      as a best-effort recency proxy instead, sorted
                      descending. Each link can appear multiple times in
                      the markup (thumbnail + headline anchors) -- the
                      extractor keeps the longest non-empty anchor text
                      seen for a given URL as the title, same pattern as
                      chinadaily-scraper / jamaicagleaner-scraper.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

BASE_URL = "https://www.guardian.co.tt"

# Matches e.g. /business/shell-stalls-aphrodite-talks-with-ngc-6.2.2652875.3d3fca7ccb
ARTICLE_URL_RE = re.compile(r"/([a-z\-]+)/[a-z0-9\-]+-6\.2\.(\d+)\.([0-9a-f]+)")

# Trinidad & Tobago is fixed AST (UTC-4) year-round -- no DST is observed.
TT_UTC_OFFSET = "-04:00"

SOFT_HYPHEN = "­"


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean(text: str | None) -> str | None:
    """Strip the CMS's invisible soft-hyphen hyphenation markers and normalize whitespace."""
    if text is None:
        return None
    return text.replace(SOFT_HYPHEN, "").strip() or None


def _find_ld_json_block(soup: BeautifulSoup, type_name: str) -> dict | None:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("@type") == type_name:
            return data
    return None


def _extract_body(soup: BeautifulSoup) -> str:
    container = soup.select_one("div.ag-article-text")
    if container is None:
        raise UnexpectedShape("No div.ag-article-text element found -- page shape has likely changed.")
    paragraphs = []
    for p in container.select("p.bodytext, p.byline"):
        text = _clean(p.get_text(" ", strip=True))
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _extract_author(soup: BeautifulSoup) -> str | None:
    author_el = soup.select_one("div.author span")
    if author_el is None:
        return None
    return _clean(author_el.get_text(" ", strip=True))


def _extract_created_time(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    """Returns (createdTimeRaw, datePublished-ISO)."""
    el = soup.select_one("span.textelement-createdtime")
    if el is None:
        return None, None
    raw = el.get_text(strip=True)
    if not re.fullmatch(r"\d{14}", raw):
        return raw, None
    iso = (
        f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}T{raw[8:10]}:{raw[10:12]}:{raw[12:14]}{TT_UTC_OFFSET}"
    )
    return raw, iso


def _extract_publish_date(soup: BeautifulSoup) -> str | None:
    el = soup.select_one("span.textelement-publishing")
    if el is None:
        return None
    raw = el.get_text(strip=True)
    return raw or None


def _extract_category(url: str) -> str | None:
    m = ARTICLE_URL_RE.search(url)
    return m.group(1) if m else None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article_body = _extract_body(soup)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    news_article = _find_ld_json_block(soup, "NewsArticle")
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    created_time_raw, date_published = _extract_created_time(soup)

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "headline": _clean(news_article.get("headline")),
        "description": _clean(news_article.get("description")),
        "articleBody": article_body,
        "author": _extract_author(soup),
        "category": _extract_category(url),
        "datePublished": date_published,
        "dateModified": news_article.get("dateModified"),
        "createdTimeRaw": created_time_raw,
        "publishDateRaw": _extract_publish_date(soup),
        "image": news_article.get("image"),
        "isAccessibleForFree": news_article.get("isAccessibleForFree"),
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
        return BASE_URL + href
    return href


def extract_latest_items(html_text: str) -> list[dict]:
    soup = BeautifulSoup(html_text, "lxml")

    titles: dict[str, str] = {}
    order: list[str] = []
    categories: dict[str, str] = {}
    article_ids: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = ARTICLE_URL_RE.search(href)
        if not m:
            continue
        norm = _normalize_url(href)
        if norm not in titles:
            order.append(norm)
            titles[norm] = ""
            categories[norm] = m.group(1)
            article_ids[norm] = m.group(2)
        # Each link can appear multiple times in the markup (a full card
        # with an <h1 class="headline">, a bare thumbnail-only anchor, a
        # "most read" sidebar entry, etc). Only trust the dedicated
        # headline element for the title -- taking the anchor's full
        # get_text() instead pulls in teaser paragraphs, "Read more"
        # link text and hidden timestamp spans from whichever card
        # variant happens to be longest, with no separators between them.
        headline_el = a.find("h1", class_="headline")
        if headline_el is not None:
            cleaned = _clean(headline_el.get_text(" ", strip=True))
            if cleaned and len(cleaned) > len(titles[norm]):
                titles[norm] = cleaned

    if not order:
        raise UnexpectedShape("No article links matched the expected URL pattern on the homepage -- page shape has likely changed.")

    order.sort(key=lambda link: int(article_ids[link]), reverse=True)

    items = []
    for link in order:
        items.append(
            {
                "_input": "latest",
                "_source": "S2-html-listing",
                "_scrapedAt": utc_now_iso(),
                "title": titles[link] or None,
                "link": link,
                "category": categories[link],
                # Best-effort recency proxy only -- the site has no date in
                # its URLs and no feed/sitemap. Fetch the article (article
                # mode) for the real datePublished.
                "articleId": article_ids[link],
            }
        )
    return items
