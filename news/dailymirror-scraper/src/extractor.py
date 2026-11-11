"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- dailymirror.lk emits ONE top-level (not @graph-wrapped)
               `application/ld+json` `NewsArticle` block per article page
               that carries the FULL `articleBody` directly -- no HTML
               body-container fallback is needed at all (unlike
               ghanaweb-scraper, which has to reconstruct the body from
               HTML because its ld+json omits articleBody). The node also
               carries `headline`, `description`, `datePublished`/
               `dateModified`, `author` (a `Person` object -- a specific
               byline name on staff-reported pieces, or the generic
               literal "DM Editorial" on many pieces), and `image` (object:
               `url`/`width`/`height` -- `url` is sometimes the bare
               literal string `"none"` when no lead image exists, and
               otherwise sometimes a relative path like
               `assets/uploads/<file>.jpeg` rather than an absolute URL).
               `articleSection` is **always** the literal string
               `"Sri Lanka"` regardless of actual section (breaking news,
               sports, business, opinion, ...) so it is useless as a
               category signal -- `category` is instead derived from the
               first path segment of the article URL (e.g.
               `breaking-news`, `school_rugby`, `sports`, `business`).
               `publisher`/`mainEntityOfPage` are static boilerplate
               (identical on every article) and are dropped rather than
               repeated on every record.
               Text fields (`headline`, `description`, `articleBody`)
               arrive with literal, undecoded HTML entities inside the
               JSON string value itself (e.g. `"...23&ndash;21 vs..."`,
               `"...development.&nbsp;"`) rather than real Unicode
               punctuation or being entity-free -- `html.unescape()` is
               applied to all three before output.
               **Quirk -- invalid raw JSON:** the ld+json blob also embeds
               literal, unescaped control characters (real newline bytes
               for `articleBody`'s paragraph breaks) directly inside JSON
               string values instead of encoding them as `\n`. Strict
               `json.loads()` rejects this with `Invalid control character`
               at the first embedded newline -- every article on the site
               fails to parse under strict mode. `json.loads(..., strict=
               False)` is required.
  S2-html-listing -- "latest" mode has no working RSS/Atom feed (`/rss`,
               `/feed`, `/rss/latest-news` all soft-redirect to the
               homepage template with HTTP 200) and no real XML sitemap
               (`/sitemap.xml`, `/sitemap-news.xml` 404; the
               robots.txt-advertised `Sitemap: https://www.dailymirror.lk
               /sitemaps` URL renders an HTML page with no link to any
               actual machine-readable sitemap file). Instead this scrapes
               the site's own Breaking News category listing page
               (`/breaking_news/108`, paginated via
               `/breaking_news/108/<offset>` in steps of 30), which is
               confirmed sorted newest-first by descending numeric article
               ID (with one exception: a pinned "live tracker" story stays
               pinned at the top of every page regardless of recency --
               see Known limits in CRAWLING_METHOD.md). Extracts `<a>`
               links matching the article URL pattern, in document order,
               deduplicated.

Soft-404 quirk (both strategies must account for this): dailymirror.lk's
router ALWAYS returns HTTP 200, never a real 404, for both a syntactically
valid article route with a non-existent numeric ID (the article-template
`NewsArticle` ld+json block is still emitted, but every field is an empty
string: `"headline":"","url":"","articleBody":""`) and a path that doesn't
match the article route pattern at all (a completely different generic
template with NO ld+json block at all). Both cases are treated identically
as `_error: "not_found"` -- see `extract_article`.
"""

import html
import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

TRAILING_IDS_RE = re.compile(r"(\d+)-(\d+)$")


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


class ArticleNotFound(Exception):
    """The router responded 200 but the page is a soft-404 (see module docstring)."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_ids(url: str) -> tuple[str | None, str | None]:
    """Returns (categoryId, articleId) from the URL's trailing `<catId>-<articleId>` segment."""
    last_segment = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    m = TRAILING_IDS_RE.search(last_segment)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def _extract_category(url: str) -> str | None:
    """First path segment of the URL, e.g. 'breaking-news', 'school_rugby', 'sports'."""
    path = url.split("://", 1)[-1].split("/", 1)
    if len(path) < 2:
        return None
    segment = path[1].split("/", 1)[0]
    return segment or None


def _find_news_article(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            # strict=False: dailymirror.lk embeds raw, unescaped control
            # characters (literal newlines) inside JSON string values (e.g.
            # articleBody's paragraph breaks), which is invalid per strict
            # JSON but readable in permissive mode.
            data = json.loads((tag.string or "").strip(), strict=False)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("@type") == "NewsArticle":
            return data
    return None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    news_article = _find_news_article(soup)
    if news_article is None:
        # Path didn't match the article route at all -- generic fallback template, no ld+json.
        raise ArticleNotFound("No NewsArticle ld+json block found on the page.")

    headline = news_article.get("headline") or ""
    body = news_article.get("articleBody") or ""
    ld_url = news_article.get("url") or ""
    if not headline and not body and not ld_url:
        # Syntactically valid route, non-existent article ID -- soft-404 template.
        raise ArticleNotFound("NewsArticle ld+json present but all fields empty (soft-404).")

    category_id, article_id = _extract_ids(url)
    author = news_article.get("author") or {}
    author_name = author.get("name") if isinstance(author, dict) else author

    return {
        "_input": url,
        "_source": "S1-jsonld",
        "_scrapedAt": utc_now_iso(),
        "articleId": article_id,
        "categoryId": category_id,
        "category": _extract_category(url),
        "headline": html.unescape(headline) if headline else headline,
        "description": html.unescape(news_article.get("description") or ""),
        "articleBody": html.unescape(body) if body else body,
        "author": author_name,
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
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


ARTICLE_LINK_RE = re.compile(r"^https://www\.dailymirror\.lk/[a-zA-Z0-9_-]+/[a-zA-Z0-9%_-]+/\d+-\d+$")


def extract_listing_items(html_text: str) -> list[dict]:
    """Parses the Breaking News category listing page (`/breaking_news/108[/<offset>]`)
    for article links, in document order (newest-first), deduplicated.

    Each article's URL appears in THREE separate <a> tags on this listing page
    (thumbnail-image link, headline link, teaser-summary link) -- the first
    occurrence in document order is always the headline-text anchor, the
    second the (longer) teaser summary, the third the image link with no
    text. Only the first non-empty text per href is kept as `title`.
    """
    soup = BeautifulSoup(html_text, "lxml")
    titles: dict[str, str] = {}
    order: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not ARTICLE_LINK_RE.match(href):
            continue
        if href not in titles:
            titles[href] = ""
            order.append(href)
        if not titles[href]:
            text = a.get_text(strip=True)
            if text:
                titles[href] = text

    if not order:
        raise UnexpectedShape("No article links found on the listing page -- page shape has likely changed.")

    results = []
    for link in order:
        category_id, article_id = _extract_ids(link)
        results.append(
            {
                "_input": "latest",
                "_source": "S2-html-listing",
                "_scrapedAt": utc_now_iso(),
                "articleId": article_id,
                "categoryId": category_id,
                "category": _extract_category(link),
                "title": html.unescape(titles[link]) if titles[link] else None,
                "link": link,
            }
        )
    return results
