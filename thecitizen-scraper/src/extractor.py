"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html    -- thecitizen.co.tz (Nation Media Group / Mwananchi
               Communications Ltd CMS, shared with Daily Nation Kenya and
               Business Daily Africa) emits TWO separate top-level ld+json
               blocks per article page: a `NewsArticle` node and a
               `BreadcrumbList` node (no `@graph` wrapper, unlike
               ghanaweb-scraper). `NewsArticle` carries `name`, `headline`,
               `description` (a short HTML-tagged teaser string, e.g.
               `"<p>...</p>"`, passed through verbatim), `image` (array of
               3 responsive-crop URLs -- landscape16x9 / landscape3x2 /
               portrait1x1 -- unlike ghanaweb's single image object),
               `datePublished`/`dateModified`, `author` (array of
               `Person` objects with `name`+`url`, always populated --
               this CMS does credit individual reporters, unlike
               GhanaWeb's `noBylinesPolicy`), and `publisher` -- but **no
               `articleBody`**.

               **Paywall metadata (key quirk):** roughly a third of
               sampled articles additionally carry
               `"isAccessibleForFree": "False"` (a JSON **string**, not a
               boolean -- verified via `type()`) plus
               `"hasPart": {"@type": "WebPageElement", "isAccessibleForFree":
               "False", "cssSelector": ".text-block"}`. This is the site's
               declared paywall signal (matches the `news:access
               ->Subscription` flag seen on the same articles in
               sitemap.xml). **However the full article body is still
               server-rendered into the HTML regardless of this flag** --
               the paywall is enforced client-side (a JS overlay + "Show
               plans" / "Subscribe" / "Register to begin your journey to
               our premium content" prompt appended after the real text),
               not at the HTTP response level. A same-length,
               same-structure `articleBody` was recovered from a
               `news:access=Subscription`-tagged article as from a free
               one (see CRAWLING_METHOD.md for the side-by-side). This
               actor still surfaces `isAccessibleForFree` on the record so
               downstream consumers can see which articles the site
               *intends* to gate, even though this scraper is not blocked
               by it.

               Full text comes from HTML:
               `div.text-block.blk-txt` (present alongside a much shorter
               `div.text-block` "what you need to know" summary box on
               some articles -- selecting the two-class combination is
               required to avoid the summary box). Paragraphs are
               `<p>` tags each wrapped in its own `<div
               class="paragraph-wrapper">`; ad slots
               (`div.content-page-ad_wrap`) and an in-body "Related"
               teaser block (`div.article-content-related`, a full
               mid-article module linking to 2 other stories) are
               siblings at the same nesting level, so selecting
               `div.paragraph-wrapper > p` specifically (rather than a
               blanket `get_text()` on the container) cleanly excludes
               both without any denylist/regex cleanup -- unlike
               ghanaweb's trailing-signature-line problem, no truncation
               heuristic was needed here.

               Category comes from `span.article-topic` (a short label,
               e.g. `"National"`, `"Football"`) plus the `BreadcrumbList`
               ld+json node (`"Home" > "News" > "National"`, etc.) which
               this extractor turns into a `categoryPath` list with
               "Home" dropped. A `section.article-content_summary`
               "What you need to know:" bullet box appears on some
               (observed: staff News/Sports pieces) but not all articles
               (observed absent on the health-insurance sample) -- kept
               as an optional `summary` field, label stripped.

  S2-sitemap -- Google News sitemap (`/sitemap.xml`, advertised via the
               single `sitemap:` line in robots.txt). Each `<url>` node
               carries `news:title`, `news:publication_date` (ISO-8601
               UTC), `news:keywords` (comma-separated, sometimes with an
               inconsistent leading space), and -- critically --
               `news:access` (`"Subscription"` when present, absent on
               free articles), the same paywall signal seen inline on the
               article page. `image:loc` carries a lead image URL. Capped
               at the ~40 newest items; no pagination offered. A plain
               `/rss.xml` feed also exists (checked, real 200, valid RSS
               2.0) but lacks the `access`/paywall field and any
               `keywords`, so the richer sitemap.xml was chosen as the
               `latest`-mode source, matching the GhanaWeb precedent of
               preferring the Google News sitemap over a plain feed when
               both exist. `section` is derived from the URL path (all
               segments between the domain and the trailing slug-id,
               e.g. `"news/national"`, `"sports/football"`, `"zanzibar"`)
               since the feed carries no separate category field.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

ARTICLE_ID_RE = re.compile(r"-(\d+)$")
WHAT_YOU_NEED_RE = re.compile(r"^what you need to know:?\s*", re.IGNORECASE)


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_article_id(url: str) -> str | None:
    m = ARTICLE_ID_RE.search(url.split("?")[0].rstrip("/"))
    return m.group(1) if m else None


def _derive_section(url: str) -> str | None:
    path = url.split("://", 1)[-1].split("/", 1)[-1]
    segments = [s for s in path.split("/") if s]
    if len(segments) <= 1:
        return None
    return "/".join(segments[:-1])


def _find_ld_node(soup: BeautifulSoup, type_name: str) -> dict | None:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("@type") == type_name:
            return data
    return None


def _extract_category_path(breadcrumb: dict | None) -> list[str]:
    if not breadcrumb:
        return []
    items = breadcrumb.get("itemListElement") or []
    names = [it.get("name") for it in items if isinstance(it, dict) and it.get("name")]
    return [n for n in names if n.lower() != "home"]


def _extract_summary(soup: BeautifulSoup) -> str | None:
    el = soup.select_one("section.article-content_summary")
    if el is None:
        return None
    text = el.get_text(" ", strip=True)
    text = WHAT_YOU_NEED_RE.sub("", text).strip()
    return text or None


def _extract_body(soup: BeautifulSoup) -> str:
    container = soup.select_one("div.text-block.blk-txt")
    if container is None:
        raise UnexpectedShape("No div.text-block.blk-txt element found -- page shape has likely changed.")

    paragraphs = []
    for p in container.select("div.paragraph-wrapper > p"):
        text = p.get_text(" ", strip=True)
        if text:
            paragraphs.append(text)

    return "\n\n".join(paragraphs)


def extract_article(html_bytes: bytes, url: str) -> dict:
    soup = BeautifulSoup(html_bytes, "lxml")

    news_article = _find_ld_node(soup, "NewsArticle")
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json node found -- page shape has likely changed.")

    article_body = _extract_body(soup)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    breadcrumb = _find_ld_node(soup, "BreadcrumbList")
    topic_el = soup.select_one("span.article-topic")
    keywords_el = soup.select_one("meta[name='keywords']")

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "articleId": _extract_article_id(url),
        "headline": news_article.get("headline") or news_article.get("name"),
        "description": news_article.get("description"),
        "articleBody": article_body,
        "summary": _extract_summary(soup),
        "category": topic_el.get_text(strip=True) if topic_el else None,
        "categoryPath": _extract_category_path(breadcrumb),
        "author": news_article.get("author"),
        "publisher": news_article.get("publisher"),
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "image": news_article.get("image"),
        "keywords": keywords_el.get("content") if keywords_el else None,
        "isAccessibleForFree": news_article.get("isAccessibleForFree"),
        "hasPart": news_article.get("hasPart"),
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
        raise UnexpectedShape("No <url> elements found in news sitemap -- feed shape has likely changed.")

    results = []
    for url_node in url_nodes:
        loc = url_node.find("loc")
        title = url_node.find("news:title")
        pub_date = url_node.find("news:publication_date")
        language = url_node.find("news:language")
        keywords = url_node.find("news:keywords")
        access = url_node.find("news:access")
        image_loc = url_node.find("image:loc")

        link = loc.text.strip() if loc and loc.text else None

        results.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "articleId": _extract_article_id(link) if link else None,
                "title": title.text.strip() if title and title.text else None,
                "link": link,
                "section": _derive_section(link) if link else None,
                "publicationDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "language": language.text.strip() if language and language.text else None,
                "keywords": keywords.text.strip() if keywords and keywords.text else None,
                "access": access.text.strip() if access and access.text else None,
                "image": image_loc.text.strip() if image_loc and image_loc.text else None,
            }
        )
    return results
