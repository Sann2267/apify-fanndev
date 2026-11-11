"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-wpapi   -- times.co.zm (WordPress 7.1, "lian-news" theme) exposes its
               standard, unauthenticated REST API at `/wp-json/wp/v2/posts`.
               Given only an article URL, the slug (the URL's last path
               segment) is queried via `?slug=<slug>&_embed=1`, which
               returns the full post in ONE round trip -- `content.rendered`
               (the complete article body as WordPress block HTML),
               `excerpt.rendered` (a short summary), plus the embedded
               author (real name, not the ld+json's generic "TIMES OF
               ZAMBIA" byline), featured-media object, and category/tag
               term objects. This is preferred over ld+json/HTML scraping
               because it's a single call, versioned, and carries a real
               per-article author name that ld+json does not expose (see
               S2 below). Paragraph markup is inconsistent across posts --
               some carry Gutenberg's `wp-block-paragraph` class, others
               (visibly LLM-authored -- see Known limits in
               CRAWLING_METHOD.md) carry a `ds-markdown-paragraph` class --
               so the extractor collects every `<p>` tag inside
               `content.rendered` unconditionally rather than filtering by
               class.
               **Key quirk (video-format posts):** posts in the "Video"
               category (slugs prefixed `watch-`) carry an empty or
               whitespace-only `content.rendered` (the real content is a
               lazy-loaded video embed, not text) -- this is genuine site
               shape, not a parse failure, so an empty `articleBody` does
               NOT raise `UnexpectedShape` here; `excerpt.rendered` still
               carries a usable summary for these posts.
  S2-jsonld+html -- fallback used only if the REST API call itself fails
               (non-200/timeout) after retries. Reads the standalone
               `NewsArticle` ld+json block (headline/dates/description/
               image -- author is always the generic `"TIMES OF ZAMBIA"`
               organization here, not an individual) plus
               `div.entry-content` on the rendered article page for the
               body text.
  S3-rss     -- default WordPress feed at `/feed/`, latest mode. 10 items
               per page, paginated via `?paged=N` for limit > 10. Carries
               `dc:creator` (real author name), full category list, and
               `content:encoded` (full body HTML, same markup-inconsistency
               caveat as S1 applies).
"""

import html
import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

SLUG_RE = re.compile(r"/([^/]+)/?$")


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slug_from_url(url: str) -> str:
    m = SLUG_RE.search(url.split("?")[0].rstrip("/"))
    if not m:
        raise UnexpectedShape(f"Could not extract a slug from URL: {url!r}")
    return m.group(1)


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


def _find_news_article_ldjson(soup: BeautifulSoup) -> dict | None:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "NewsArticle":
            return data
    return None


def extract_article_wpapi(post: dict, url: str) -> dict:
    """S1-wpapi -- parse one item from /wp-json/wp/v2/posts?slug=...&_embed=1."""
    if "content" not in post or "rendered" not in post.get("content", {}):
        raise UnexpectedShape(f"WP API post is missing content.rendered -- got keys={list(post.keys())}")

    embedded = post.get("_embedded") or {}

    author_obj = (embedded.get("author") or [{}])[0]
    author_name = author_obj.get("name")
    author_slug = author_obj.get("slug")
    author_link = author_obj.get("link")

    media_list = embedded.get("wp:featuredmedia") or []
    media_obj = media_list[0] if media_list and not media_list[0].get("code") else None
    featured_image = None
    if media_obj:
        details = media_obj.get("media_details") or {}
        featured_image = {
            "url": media_obj.get("source_url"),
            "width": details.get("width"),
            "height": details.get("height"),
            "altText": media_obj.get("alt_text") or None,
        }

    categories: list[str] = []
    tags: list[str] = []
    for group in embedded.get("wp:term") or []:
        for term in group:
            if not isinstance(term, dict):
                continue
            if term.get("taxonomy") == "category":
                categories.append(term.get("name"))
            elif term.get("taxonomy") == "post_tag":
                tags.append(term.get("name"))

    content = post.get("content") or {}
    excerpt = post.get("excerpt") or {}

    return {
        "_input": url,
        "_source": "S1-wpapi",
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
        "author": author_name,
        "authorSlug": author_slug,
        "authorLink": author_link,
        "categories": categories,
        "tags": tags,
        "featuredImage": featured_image,
        "guid": (post.get("guid") or {}).get("rendered"),
        "contentProtected": content.get("protected"),
    }


def extract_article_html_fallback(html_text: str, url: str) -> dict:
    """S2-jsonld+html -- used only when the WP REST API call itself fails."""
    soup = BeautifulSoup(html_text, "lxml")

    article = _find_news_article_ldjson(soup)
    if article is None:
        raise UnexpectedShape("No standalone NewsArticle ld+json block found -- page shape has likely changed.")

    body_div = soup.select_one("div.entry-content")
    if body_div is None:
        raise UnexpectedShape("div.entry-content not found -- page shape has likely changed.")

    paragraphs = [p.get_text(" ", strip=True) for p in body_div.find_all("p") if p.get_text(strip=True)]
    article_body = "\n\n".join(paragraphs) if paragraphs else None

    author = article.get("author")
    author_name = author.get("name") if isinstance(author, dict) else author

    image = article.get("image")
    image_url = image if isinstance(image, str) else (image.get("url") if isinstance(image, dict) else None)

    return {
        "_input": url,
        "_source": "S2-jsonld+html",
        "_scrapedAt": utc_now_iso(),
        "headline": article.get("headline"),
        "description": article.get("description"),
        "articleBody": article_body,
        "date": article.get("datePublished"),
        "modified": article.get("dateModified"),
        "author": author_name,
        "featuredImage": {"url": image_url} if image_url else None,
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
    """S3-rss -- one page (10 items) of /feed/ or /feed/?paged=N."""
    soup = BeautifulSoup(xml_bytes, "xml")
    items = soup.find_all("item")
    if not items:
        raise UnexpectedShape("No <item> elements found in RSS feed -- feed shape has likely changed.")
    results = []
    for item in items:
        title = item.find("title")
        link = item.find("link")
        creator = item.find("dc:creator") or item.find("creator")
        guid = item.find("guid")
        pub_date = item.find("pubDate")
        description = item.find("description")
        encoded = item.find("content:encoded") or item.find("encoded")
        categories = [c.text.strip() for c in item.find_all("category") if c.text]
        results.append(
            {
                "_input": "latest",
                "_source": "S3-rss",
                "_scrapedAt": utc_now_iso(),
                "title": _clean_html_text(title.text) if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "author": creator.text.strip() if creator and creator.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "description": _clean_html_text(description.text if description else None),
                "articleBody": _paragraphs_from_html(encoded.text if encoded else None),
                "categories": categories,
            }
        )
    return results
