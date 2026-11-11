"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-wpapi-by-id -- daily-mail.co.zm (WordPress 6.3.2, OceanWP theme +
               Elementor page builder) exposes its standard, unauthenticated
               REST API, but the **collection** endpoint
               (`/wp-json/wp/v2/posts?slug=...`) silently ignores every
               query string and always returns the same unfiltered "latest
               10" list -- confirmed dead end (see constants.py docstring).
               Instead: fetch the article's own HTML page, read the numeric
               post ID out of the standard WordPress REST-discovery link
               (`<link rel="alternate" type="application/json"
               href=".../wp-json/wp/v2/posts/<id>">` in `<head>`), then hit
               the **singular** `/wp-json/wp/v2/posts/<id>` endpoint, which
               (unlike the collection endpoint) reliably returns the correct
               post. Author/featured-image/category/tag names are resolved
               with one follow-up singular-endpoint call each
               (`/wp-json/wp/v2/{users,media,categories,tags}/<id>`) run
               concurrently -- `_embed=1` was tried and does NOT work on
               this site (the `_embedded` key never appears in the response
               even though the `_links` section advertises `embeddable:
               true` hrefs), so embedding has to be done manually.
               Real reporter bylines (e.g. "MARY LEMBA, Lusaka") are NOT in
               the WordPress author field here -- this site has only two WP
               users ("webmaster", "Website Editor") -- they're written into
               the first paragraph of the article body itself, same as many
               state-press outlets in this portfolio. `author`/`authorName`
               on S1 records is therefore almost always the generic
               "Website Editor", not an individual.
  S2-html    -- fallback used only if the initial HTML fetch fails, the
               REST-discovery link is missing, or the singular by-ID API
               call fails. This site carries NO ld+json NewsArticle block
               and NO Open Graph meta tags at all (confirmed absent on every
               sampled article) -- unlike most WordPress sites in this
               portfolio, there is no SEO plugin (Yoast/Rank Math) active.
               So S2 reads the raw Elementor-rendered HTML directly:
               `div[data-widget_type^="theme-post-content"]
               .elementor-widget-container` for the body paragraphs, the
               `elementor-widget-theme-post-title` heading for the headline,
               and the `elementor-post-info__item--type-date` /
               `--type-time` spans for the publish date (parsed from
               "Month D, YYYY" + "H:MM am/pm" text -- no ISO datetime
               attribute is present, so this is a best-effort local-time
               parse). No description/author/categories are available on
               this path.
  S3-archive -- latest mode. `/category/headlines/` (category id 18, present
               on every sampled post -- effectively this site's global
               latest-news feed; the RSS feed and REST collection endpoint
               are both stuck on a static top-10, see constants.py) paginated
               via `/category/headlines/page/N/`. Carries title, link, real
               WP author name (almost always "Website Editor", see above),
               a plain-text publish date (no time-of-day on this listing
               page), category names, a short excerpt, and a thumbnail --
               NOT the full article body (would require one extra fetch per
               item; use "article" mode for full text).
"""

import html
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

JSONLD_DISCOVERY_RE = re.compile(
    r'<link\s+rel=["\']alternate["\']\s+type=["\']application/json["\']\s+href=["\']([^"\']+/wp-json/wp/v2/posts/\d+)["\']'
)

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_html_text(raw: str | None) -> str | None:
    """Single-block text (title, excerpt): unescape, strip tags, collapse whitespace."""
    if not raw:
        return None
    unescaped = html.unescape(raw)
    text = BeautifulSoup(unescaped, "lxml").get_text(" ", strip=True)
    return text or None


def _paragraphs_from_html(raw: str | None) -> str | None:
    """Multi-paragraph body: join each <p> as its own line, blank line between."""
    if not raw or not raw.strip():
        return None
    soup = BeautifulSoup(html.unescape(raw), "lxml")
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
    return "\n\n".join(paragraphs) if paragraphs else None


def discover_post_id(html_text: str) -> int | None:
    """Read the numeric post ID out of the WordPress REST-discovery <link> in <head>."""
    m = JSONLD_DISCOVERY_RE.search(html_text)
    if not m:
        return None
    api_url = m.group(1)
    id_m = re.search(r"/posts/(\d+)$", api_url)
    return int(id_m.group(1)) if id_m else None


def _parse_local_datetime(date_text: str | None, time_text: str | None) -> str | None:
    """Best-effort parse of S2's 'Month D, YYYY' + 'H:MM am/pm' text into an ISO string.

    No timezone indicator is present anywhere on the page -- this is left
    naive (no 'Z'/offset suffix), matching how S1's own 'date' field (as
    opposed to 'date_gmt') is also emitted without an offset.
    """
    if not date_text:
        return None
    m = re.match(r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})", date_text.strip())
    if not m:
        return None
    month = MONTHS.get(m.group(1).lower())
    if not month:
        return None
    day, year = int(m.group(2)), int(m.group(3))
    hour, minute = 0, 0
    if time_text:
        tm = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)", time_text.strip(), re.I)
        if tm:
            hour, minute = int(tm.group(1)), int(tm.group(2))
            if tm.group(3).lower() == "pm" and hour != 12:
                hour += 12
            elif tm.group(3).lower() == "am" and hour == 12:
                hour = 0
    return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00"


def extract_article_wpapi(
    post: dict,
    url: str,
    author: dict | None,
    media: dict | None,
    categories: list[dict],
    tags: list[dict],
) -> dict:
    """S1-wpapi-by-id -- parse a single item from /wp-json/wp/v2/posts/<id>."""
    if "content" not in post or "rendered" not in post.get("content", {}):
        raise UnexpectedShape(f"WP API post is missing content.rendered -- got keys={list(post.keys())}")

    featured_image = None
    if media:
        details = media.get("media_details") or {}
        featured_image = {
            "url": media.get("source_url"),
            "width": details.get("width"),
            "height": details.get("height"),
            "altText": media.get("alt_text") or None,
        }

    content = post.get("content") or {}
    excerpt = post.get("excerpt") or {}

    return {
        "_input": url,
        "_source": "S1-wpapi-by-id",
        "_scrapedAt": utc_now_iso(),
        "id": post.get("id"),
        "slug": post.get("slug"),
        "link": post.get("link"),
        "headline": _clean_html_text((post.get("title") or {}).get("rendered")),
        "description": _clean_html_text(excerpt.get("rendered")),
        "articleBody": _paragraphs_from_html(content.get("rendered")),
        "date": post.get("date"),
        "date_gmt": post.get("date_gmt"),
        "modified": post.get("modified"),
        "modified_gmt": post.get("modified_gmt"),
        "author": author.get("name") if author else None,
        "authorId": post.get("author"),
        "authorSlug": author.get("slug") if author else None,
        "authorLink": author.get("link") if author else None,
        "categories": [c.get("name") for c in categories if c],
        "tags": [t.get("name") for t in tags if t],
        "featuredImage": featured_image,
        "guid": (post.get("guid") or {}).get("rendered"),
        "contentProtected": content.get("protected"),
    }


def extract_article_html_fallback(html_text: str, url: str) -> dict:
    """S2-html -- used only when the discovery-link/by-ID API path fails.

    No ld+json, no Open Graph meta on this site (see module docstring) --
    reads the raw Elementor-rendered markup directly.
    """
    soup = BeautifulSoup(html_text, "lxml")

    title_el = soup.select_one(".elementor-widget-theme-post-title .elementor-heading-title") or soup.find("h1")
    if title_el is None:
        raise UnexpectedShape("No post-title heading found -- page shape has likely changed.")
    headline = title_el.get_text(" ", strip=True)

    body_container = soup.select_one('div[data-widget_type^="theme-post-content"] .elementor-widget-container')
    if body_container is None:
        raise UnexpectedShape("theme-post-content widget not found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in body_container.find_all("p") if p.get_text(strip=True)]
    article_body = "\n\n".join(paragraphs) if paragraphs else None

    date_el = soup.select_one(".elementor-post-info__item--type-date")
    time_el = soup.select_one(".elementor-post-info__item--type-time")
    date_text = date_el.get_text(" ", strip=True) if date_el else None
    time_text = time_el.get_text(" ", strip=True) if time_el else None

    return {
        "_input": url,
        "_source": "S2-html",
        "_scrapedAt": utc_now_iso(),
        "headline": headline,
        "articleBody": article_body,
        "date": _parse_local_datetime(date_text, time_text),
        "dateText": date_text,
        "timeText": time_text,
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_latest_items(html_text: str) -> list[dict]:
    """S3-archive -- one page (10 items) of /category/headlines/ or /category/headlines/page/N/."""
    soup = BeautifulSoup(html_text, "lxml")
    articles = soup.find_all("article")
    if not articles:
        raise UnexpectedShape("No <article> cards found on the category archive page -- page shape has likely changed.")

    results = []
    for art in articles:
        title_a = art.select_one(".blog-entry-title a")
        if title_a is None:
            continue
        link = title_a.get("href")
        title = title_a.get_text(" ", strip=True)

        post_id = None
        for cls in art.get("class", []):
            m = re.match(r"post-(\d+)$", cls)
            if m:
                post_id = int(m.group(1))
                break

        author_a = art.select_one(".meta-author a")
        date_li = art.select_one(".meta-date")
        cat_links = art.select(".meta-cat a")
        excerpt_p = art.select_one(".blog-entry-summary p")
        thumb_img = art.select_one(".thumbnail img")

        # .meta-date includes a leading screen-reader-only "Post published:"
        # span -- strip it before reading the visible date text.
        pub_date = None
        if date_li:
            sr = date_li.find("span", class_="screen-reader-text")
            if sr:
                sr.extract()
            pub_date = date_li.get_text(" ", strip=True)

        results.append(
            {
                "_input": "latest",
                "_source": "S3-archive",
                "_scrapedAt": utc_now_iso(),
                "postId": post_id,
                "title": title,
                "link": link,
                "author": author_a.get_text(" ", strip=True) if author_a else None,
                "authorLink": author_a.get("href") if author_a else None,
                "pubDate": pub_date,
                "categories": [c.get_text(" ", strip=True) for c in cat_links],
                "description": excerpt_p.get_text(" ", strip=True) if excerpt_p else None,
                "thumbnail": thumb_img.get("src") if thumb_img else None,
            }
        )
    return results
