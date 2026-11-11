"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-wpapi   -- thisdaylive.com (WordPress, W3 Total Cache + CloudFront)
               exposes its standard, unauthenticated REST API at
               `/wp-json/wp/v2/posts`. Given only an article URL, the slug
               (the URL's last path segment) is queried via
               `?slug=<slug>&_embed=1`, which returns the full post in ONE
               round trip -- `content.rendered` (the complete article body
               as WordPress block/classic HTML), `excerpt.rendered` (a
               short teaser), plus the embedded author (real name),
               featured-media object, and category/tag term objects. This
               is the ONLY strategy needed on this site because the article
               HTML carries **no JSON-LD at all** (confirmed across 4
               sampled article pages spanning News/Sport/Education/Metro --
               zero `<script type="application/ld+json">` blocks anywhere)
               and almost no OpenGraph metadata either (only `og:image` is
               present; `og:title`/`og:description`/`article:published_time`
               are all absent) -- the REST API is the only rich structured
               source this site offers.
               Same strategy, same endpoint (`?per_page=<limit>&_embed=1`,
               no `slug` filter), also powers **latest mode** -- unlike
               most actors in this portfolio, latest-mode records here
               carry the exact same rich shape as article-mode records
               (full `articleBody`, real author, categories/tags), not a
               thin title/link/pubDate shape, because the RSS feed this
               site would normally offer for that purpose is broken (see
               S2 below) and the REST API itself is a perfectly good latest-
               headlines source (`per_page` up to 50 confirmed working in a
               single call, no pagination loop needed).
               **Key quirk (empty title/slug posts):** a small number of
               posts (observed: 1 out of 20 sampled) have an EMPTY
               `title.rendered` and a numeric-only `slug` (e.g. `"slug":
               "1240482"`, the post's own ID) despite carrying a full,
               real `content.rendered` body -- looks like a
               publish-workflow glitch on the CMS side (an unfinished/
               unpublished-then-force-published draft), not a parse
               failure. `headline` is legitimately `None`/empty for these;
               NOT treated as `UnexpectedShape`.
  S2-html    -- fallback used only if the REST API call itself fails
               (non-200/timeout) after retries. thisdaylive.com has NO
               ld+json and almost no OpenGraph metadata (see above), so
               this fallback is HTML-only and materially poorer than S1: it
               reads `<title>` (site name suffix stripped) for the
               headline and `section#single_article div.article-content`
               for the body text -- there is no reliable author, date, or
               description source anywhere in the raw HTML on this site,
               so those fields are always `None` on this path.
"""

import html
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

SLUG_RE = re.compile(r"/([^/]+)/?$")
TITLE_SUFFIX_RE = re.compile(r"\s*[–—|]\s*THISDAYLIVE\s*$", re.IGNORECASE)


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
    if raw is None:
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


def extract_article_wpapi(post: dict, input_value: str) -> dict:
    """S1-wpapi -- parse one item from /wp-json/wp/v2/posts (article or latest mode)."""
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
        "_input": input_value,
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
    """S2-html -- used only when the WP REST API call itself fails. No
    ld+json and almost no OpenGraph metadata exist on this site, so this
    path is degraded: headline + body only, no author/date/description.
    """
    soup = BeautifulSoup(html_text, "lxml")

    body_container = soup.select_one("section#single_article div.article-content")
    if body_container is None:
        raise UnexpectedShape("section#single_article div.article-content not found -- page shape has likely changed.")

    paragraphs = [p.get_text(" ", strip=True) for p in body_container.find_all("p") if p.get_text(strip=True)]
    article_body = "\n\n".join(paragraphs) if paragraphs else None
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    title_tag = soup.title
    headline = None
    if title_tag and title_tag.text:
        headline = TITLE_SUFFIX_RE.sub("", title_tag.text.strip()).strip() or None
    if not headline:
        h1 = soup.select_one("section#single_article h1")
        headline = h1.get_text(strip=True) if h1 else None

    return {
        "_input": url,
        "_source": "S2-html",
        "_scrapedAt": utc_now_iso(),
        "headline": headline,
        "description": None,
        "articleBody": article_body,
        "date": None,
        "author": None,
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
