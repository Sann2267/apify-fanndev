"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- jamaicaobserver.com emits a `NewsArticle` ld+json block
                    with `headline`, `datePublished`, `dateModified`,
                    `image`, `isAccessibleForFree`, and `articleSection` --
                    but no `articleBody` or `author`. Full text comes from
                    HTML `div.content-single-wrap` (confirmed a UNIQUE class
                    combination on the page -- unlike the bare `body` class
                    it also carries, which matches 9 unrelated containers),
                    direct-child `<p>` tags only (`recursive=False`) --
                    confirmed clean on 3 samples, no ad/related-article
                    paragraphs mixed in even though non-`<p>` sibling `<div>`
                    elements (images/embeds) are interleaved between
                    paragraphs.

                    `articleSection` sometimes carries a literal
                    double-HTML-escaped `&amp;` (e.g. `"Art &amp; Culture"`)
                    -- `html.unescape()` is applied to every text value
                    pulled from the graph for robustness.

                    No author byline was found anywhere on any sampled
                    article page (no meta tag, no visible byline element --
                    a `.date_with_author` CSS rule exists in the theme's
                    stylesheet but the corresponding HTML element is never
                    rendered). The WordPress REST API
                    (`/wp-json/wp/v2/posts?slug=...`) resolves `author` to a
                    single generic "tecnavia" import/syndication account on
                    every article sampled, not the real byline -- so it is
                    NOT used as an author source either. `author` is
                    intentionally omitted from article-mode output rather
                    than fabricated; the real reporter byline (name + title
                    + email in one string) is only available via `latest`
                    mode's RSS `dc:creator` field.
  S2-rss          -- `/feed/`, the standard WordPress RSS 2.0 feed --
                    confirmed working cleanly (37 items per fetch), unlike
                    jamaicagleaner-scraper's sibling site where both
                    sitemap.xml and rss.xml are broken. Carries `title`,
                    `link`, `pubDate`, `dc:creator` (real byline string),
                    `category`, and full `content:encoded` HTML body.
"""

import html
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _unescape(value):
    if isinstance(value, str):
        return html.unescape(value)
    if isinstance(value, list):
        return [_unescape(v) for v in value]
    return value


def _find_news_article(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("@type") == "NewsArticle":
            return data
    return None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    body_el = soup.select_one("div.content-single-wrap")
    if body_el is None:
        raise UnexpectedShape("No div.content-single-wrap element found -- page shape has likely changed.")
    paragraphs = [
        p.get_text(" ", strip=True) for p in body_el.find_all("p", recursive=False)
    ]
    paragraphs = [p for p in paragraphs if p]
    article_body = "\n\n".join(paragraphs)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    article = _find_news_article(soup)
    if article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    is_free = article.get("isAccessibleForFree")

    return {
        "_input": url,
        "_source": "S1-jsonld+html",
        "_scrapedAt": utc_now_iso(),
        "headline": _unescape(article.get("headline")),
        "articleBody": article_body,
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "image": article.get("image"),
        "articleSection": _unescape(article.get("articleSection")),
        "isAccessibleForFree": is_free,
        "_paywalled": is_free is False,
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_rss_items(xml_text: str) -> list[dict]:
    soup = BeautifulSoup(xml_text, "xml")
    items = []
    for item in soup.find_all("item"):
        title = item.find("title")
        link = item.find("link")
        guid = item.find("guid")
        creator = item.find("dc:creator") or item.find("creator")
        category = item.find("category")
        pub_date = item.find("pubDate")
        content_encoded = item.find("content:encoded") or item.find("encoded")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": html.unescape(title.text.strip()) if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "creator": creator.text.strip() if creator and creator.text else None,
                "category": category.text.strip() if category and category.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "contentEncoded": content_encoded.text.strip() if content_encoded and content_encoded.text else None,
            }
        )
    return items
