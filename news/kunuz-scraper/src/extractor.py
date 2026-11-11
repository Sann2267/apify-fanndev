"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- kun.uz (English edition, `/en/news/<date>/<slug>`)
             emits a `NewsArticle` ld+json block plus a `BreadcrumbList`
             block -- the extractor scans all ld+json blocks and picks
             the one whose `@type` is `NewsArticle`. That block carries
             `headline`, `description`, `image` (list), `datePublished`,
             `dateModified`, `author` (Person), `publisher`
             (Organization) -- but **no `articleBody`**. Full text
             comes from HTML `div.article-body > div.container > p`.
  S1b-custom-page -- a small minority of articles (long-read/listicle
             features) are built with a Tilda-style page builder
             instead of the standard template and have **no**
             `div.article-body` at all. Body text is reconstructed by
             joining every `div.ql-editor` block's text in document
             order instead (see CRAWLING_METHOD.md).
  S2-listing -- `/en/news/list`, the site's dedicated SSR "Latest news"
             page -- title/link/thumbnail only, no article body (a
             follow-up `article`-mode fetch is needed for full text).

**Byline quirk**: even on the English edition, `author.name` from the
ld+json is consistently in Cyrillic (Russian or Uzbek Cyrillic script,
e.g. "Дониёр Тухсинов") -- kept as raw passthrough, not translated.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_text(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _unescape(text):
    if isinstance(text, str):
        import html as _html

        return _html.unescape(text)
    return text


def _find_news_article(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("@type") == "NewsArticle":
            return data
    return None


def _images_from_ld(news_article: dict) -> list[str]:
    image = news_article.get("image")
    if isinstance(image, dict):
        image = [image]
    elif isinstance(image, str):
        image = [image]
    elif not isinstance(image, list):
        image = []
    out = []
    for img in image:
        if isinstance(img, dict) and img.get("url"):
            out.append(img["url"])
        elif isinstance(img, str):
            out.append(img)
    return out


def _extract_body(soup: BeautifulSoup) -> tuple[str | None, str]:
    """Returns (article_body, strategy_suffix)."""
    body_el = soup.select_one("div.article-body")
    if body_el is not None:
        paragraphs = [p.get_text(" ", strip=True) for p in body_el.find_all("p")]
        paragraphs = [p for p in paragraphs if p]
        text = "\n\n".join(paragraphs)
        if text:
            return text, ""

    # S1b fallback -- "custom-page" long-read/listicle template built
    # with a Tilda-style page builder, no div.article-body at all.
    editor_blocks = soup.select("div.ql-editor")
    if editor_blocks:
        parts = [b.get_text(" ", strip=True) for b in editor_blocks]
        parts = [p for p in parts if p]
        text = "\n\n".join(parts)
        if text:
            return text, "b-custom-page"

    return None, ""


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article_body, strategy_suffix = _extract_body(soup)
    if not article_body:
        title_el = soup.select_one("title")
        page_title = title_el.get_text(strip=True) if title_el else None
        raise UnexpectedShape(
            "No div.article-body or div.ql-editor content found -- page shape has likely "
            f"changed (or a one-off bad edge response, see UNEXPECTED_SHAPE_RETRIES in "
            f"main.py). len={len(html_text)} title={page_title!r}"
        )

    news_article = _find_news_article(soup)
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    author = news_article.get("author") or {}
    author_name = author.get("name") if isinstance(author, dict) else author
    publisher = news_article.get("publisher") or {}
    publisher_name = publisher.get("name") if isinstance(publisher, dict) else publisher

    source = "S1b-custom-page" if strategy_suffix else "S1-jsonld+html"

    return {
        "_input": url,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "headline": _unescape(news_article.get("headline")),
        "description": _unescape(news_article.get("description")),
        "articleBody": _unescape(article_body),
        "author": _unescape(author_name),
        "publisher": _unescape(publisher_name),
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "images": _images_from_ld(news_article),
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_listing_items(html_text: str) -> list[dict]:
    """Parses /en/news/list -- the site's dedicated SSR "Latest news"
    page. Title/link/thumbnail/date only (no article body); confirmed
    genuinely newest-first against real `datePublished` timestamps
    during recon (see CRAWLING_METHOD.md)."""
    soup = BeautifulSoup(html_text, "lxml")
    items = []
    seen_links = set()

    time_re = re.compile(r"(\d{2}):(\d{2})\s*/\s*(\d{2})\.(\d{2})\.(\d{4})")

    for a in soup.select('a[href*="/en/news/"]'):
        href = a.get("href") or ""
        m = re.match(r"^(/en/news/(\d{4})/(\d{2})/(\d{2})/[a-z0-9\-]+)$", href)
        if not m:
            continue
        link = "https://kun.uz" + m.group(1)
        if link in seen_links:
            continue

        # The listing markup wraps each item in a bare <li><a>...</a></li>
        # -- no thumbnail image on this page (unlike the homepage's
        # curated sections). title comes from the nested <h3>; a
        # "HH:MM / DD.MM.YYYY" timestamp span (site-local, UTC+5, same
        # offset observed in article ld+json) sits alongside it and is
        # parsed into a proper ISO datetime -- more precise than the
        # calendar date alone available from the URL slug.
        container = a.find_parent("li") or a
        title_el = container.select_one("h1, h2, h3, [class*='title']")

        title = _clean_text(title_el.get_text(" ", strip=True)) if title_el else None
        if not title:
            title = _clean_text(a.get_text(" ", strip=True)) or None
        if not title:
            # Skip nav/footer links that matched the href pattern but
            # carry no visible headline text (e.g. icon-only links).
            continue

        published_at = None
        tm = time_re.search(container.get_text(" ", strip=True))
        if tm:
            hh, mm, dd, mo, yyyy = tm.groups()
            published_at = f"{yyyy}-{mo}-{dd}T{hh}:{mm}:00+05:00"

        seen_links.add(link)
        items.append(
            {
                "_input": "latest",
                "_source": "S2-listing",
                "_scrapedAt": utc_now_iso(),
                "title": title,
                "link": link,
                "publishedAt": published_at,
                "publishedDate": f"{m.group(2)}-{m.group(3)}-{m.group(4)}",
            }
        )

    if not items:
        raise UnexpectedShape("No /en/news/<date>/<slug> links found on listing page -- page shape has likely changed.")

    return items
