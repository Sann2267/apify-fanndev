"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- independent.co.uk (React/styled-components frontend)
               emits a `NewsArticle` ld+json block with rich metadata
               (headline, description, author, dates, isAccessibleForFree,
               image) but **no `articleBody` field at all** -- unlike most
               of this portfolio, metadata and body text must come from two
               different places. Body text is scraped from HTML: every
               `<p>` tag inside the page's `<article>` element, with a
               fixed set of known **UI boilerplate paragraphs filtered out
               by prefix match** ("Please refresh the page...", "I would
               like to be emailed about offers...", "Join thought-provoking
               conversations...", "Removed from bookmarks", "Show
               comments") -- these are login-prompt/newsletter-signup/
               comment-CTA strings baked into the same `<article>`
               container as the real paragraphs, not wrapped in any
               distinguishing class. Real body paragraphs sit in a
               styled-components div with a hash class name
               (`sc-14x1gfp-0` at time of writing) that is NOT used for
               selection (styled-component hashes rotate on redeploy) --
               filtering by boilerplate text content is more durable here
               than filtering by class name.
               `isAccessibleForFree` was `true` on all 3 sampled articles
               (sport, world news, Asia) -- no premium/metered article was
               found in this recon, so **paywall handling is unverified**;
               if a `false` value is ever seen, the record still emits
               whatever paragraphs are present (no truncation was found in
               samples either way).
  S2-sitemap  -- Google News sitemap (`/sitemaps/googlenews`, advertised in
               robots.txt). Rich shape: `news:title`, `news:publication_date`,
               `news:keywords` (comma-separated), `lastmod`, and one
               `image:image` block per entry.
"""

import html
from datetime import datetime, timezone
import json

from bs4 import BeautifulSoup

BOILERPLATE_PREFIXES = (
    "Please refresh the page",
    "I would like to be emailed about offers",
    "Removed from bookmarks",
    "Join thought-provoking conversations",
    "Show comments",
)


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_news_article(soup: BeautifulSoup) -> dict | None:
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


def _extract_body_paragraphs(soup: BeautifulSoup) -> str:
    article = soup.find("article")
    if article is None:
        return ""
    paragraphs = []
    for p in article.find_all("p"):
        text = p.get_text(" ", strip=True)
        if not text or any(text.startswith(prefix) for prefix in BOILERPLATE_PREFIXES):
            continue
        paragraphs.append(text)
    return "\n\n".join(paragraphs)


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article = _find_news_article(soup)
    if article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    article_body = _extract_body_paragraphs(soup)
    if not article_body:
        raise UnexpectedShape("No body paragraphs found in <article> -- page shape has likely changed.")

    author = article.get("author")
    author_name = author.get("name") if isinstance(author, dict) else None

    image = article.get("image")
    if isinstance(image, dict):
        image_url = image.get("url")
    elif isinstance(image, list) and image:
        first = image[0]
        image_url = first.get("url") if isinstance(first, dict) else first
    else:
        image_url = None

    return {
        "_input": url,
        "_source": "S1-jsonld+html",
        "_scrapedAt": utc_now_iso(),
        "headline": article.get("headline"),
        "description": article.get("description"),
        "articleBody": article_body,
        "articleSection": article.get("articleSection"),
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "author": author_name,
        "isAccessibleForFree": article.get("isAccessibleForFree"),
        "image": image_url,
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
    items = []
    for url_node in soup.find_all("url"):
        loc = url_node.find("loc")
        title = url_node.find("news:title")
        pub_date = url_node.find("news:publication_date")
        keywords = url_node.find("news:keywords")
        image = url_node.find("image:loc")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": loc.text.strip() if loc and loc.text else None,
                "publicationDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "keywords": [k.strip() for k in keywords.text.split(",")] if keywords and keywords.text else [],
                # image:loc is wrapped in a CDATA block -- entities inside CDATA
                # are NOT XML-decoded by the parser, so the query string's "&"
                # arrives literally as "&amp;" and needs one manual unescape.
                "imageUrl": html.unescape(image.text.strip()) if image and image.text else None,
            }
        )
    return items
