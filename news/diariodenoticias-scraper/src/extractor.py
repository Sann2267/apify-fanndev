"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- dn.pt (Quintype CMS) emits FIVE separate top-level
               `<script type="application/ld+json">` tags per article page
               (BreadcrumbList, WebPage, SiteNavigationElement, Person,
               NewsArticle) -- unlike ghanaweb-scraper's single `@graph`
               array, each is its own standalone JSON document, so the
               extractor scans all ld+json tags and picks the one whose
               `@type` is `NewsArticle`. That node carries a genuinely
               complete `articleBody` (full plain text, no truncation --
               see paywall note below), `headline`, `description`,
               `datePublished`/`dateModified`/`dateCreated`, `keywords`
               (comma-separated string, not an array), `articleSection`,
               `author` (an ARRAY of `Person` objects -- even for a single
               byline), `image` (an ARRAY of `ImageObject` -- DN serves 3
               crop variants: 16:9, 4:3, 1:1 -- vs. ghanaweb's single
               object), and `thumbnailUrl`.

               **Paywall marker (soft paywall, confirmed):** premium
               articles carry `"isAccessibleForFree": false` plus a
               `"hasPart": [{"@type": "WebPageElement",
               "isAccessibleForFree": false, "cssSelector": ".paywall"}]`
               entry -- the standard schema.org soft-paywall pattern (same
               family as NYT/WaPo). Free articles omit `isAccessibleForFree`
               entirely (it's simply absent, not `true`). Critically,
               `articleBody` is the SAME full, untruncated text regardless
               of this flag -- verified on a `access:"subscription"`
               article (confirmed via the site's own embedded Quintype
               state blob, `qt.data.story.access`) where `articleBody` ran
               6983 characters, matching the length delivered in the
               site's own `/stories.rss` `<content:encoded>` for the same
               piece. This is a pure client-side JS paywall overlay; the
               server-rendered HTML/ld+json is not gated. The extractor
               surfaces this as a derived `_paywalled` boolean so
               downstream consumers can filter/flag premium content
               without losing the text.
  S2-rss     -- `/stories.rss` (found via the `/feed` -> `/stories.rss`
               redirect; not advertised in robots.txt, unlike the Google
               News sitemap which is). Standard RSS 2.0 with Atom/media
               extensions. `<content:encoded>` already carries the
               (near-)full article body as HTML -- plain-text length
               matched the corresponding article page's ld+json
               `articleBody` within ~1% on the one article sampled in
               depth (whitespace/formatting differences only). Only ~17
               items are present in one fetch (no offset/paging param
               found), but the feed updates near-real-time (freshest
               sampled item was ~25 minutes old at fetch time).
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

ARTICLE_ID_RE = re.compile(r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})")


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_ldjson_node(soup: BeautifulSoup, type_name: str) -> dict | None:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if isinstance(node, dict) and node.get("@type") == type_name:
                return node
    return None


def _derive_paywalled(news_article: dict) -> bool:
    """dn.pt runs a soft (metered/client-side) paywall -- see module
    docstring. `isAccessibleForFree` is only emitted (as `false`) on
    premium articles; free articles omit the key entirely."""
    if news_article.get("isAccessibleForFree") is False:
        return True
    for part in news_article.get("hasPart") or []:
        if isinstance(part, dict) and part.get("cssSelector") == ".paywall":
            return True
    return False


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    news_article = _find_ldjson_node(soup, "NewsArticle")
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json node found -- page shape has likely changed.")

    article_body = news_article.get("articleBody")
    if not article_body:
        raise UnexpectedShape("articleBody missing/empty in ld+json -- page shape has likely changed.")

    return {
        "_input": url,
        "_source": "S1-jsonld",
        "_scrapedAt": utc_now_iso(),
        "_paywalled": _derive_paywalled(news_article),
        # Raw passthrough of the NewsArticle ld+json node (see
        # conventions/dataset-envelope.md) -- field names/shapes kept
        # exactly as dn.pt emits them (author/image are arrays, keywords
        # is a comma-separated string, not a list).
        "headline": news_article.get("headline"),
        "alternativeHeadline": news_article.get("alternativeHeadline"),
        "description": news_article.get("description"),
        "articleBody": article_body,
        "author": news_article.get("author"),
        "keywords": news_article.get("keywords"),
        "articleSection": news_article.get("articleSection"),
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "dateCreated": news_article.get("dateCreated"),
        "inLanguage": news_article.get("inLanguage"),
        "thumbnailUrl": news_article.get("thumbnailUrl"),
        "image": news_article.get("image"),
        "publisher": news_article.get("publisher"),
        "mainEntityOfPage": news_article.get("mainEntityOfPage"),
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
    soup = BeautifulSoup(xml_bytes, "xml")
    item_nodes = soup.find_all("item")
    if not item_nodes:
        raise UnexpectedShape("No <item> elements found in stories.rss -- feed shape has likely changed.")

    results = []
    for item in item_nodes:
        title = item.find("title")
        link = item.find("link")
        guid = item.find("guid")
        pub_date = item.find("pubDate")
        author = item.find("atom:author") or item.find("author")
        author_name = None
        if author is not None:
            name_tag = author.find("atom:name") or author.find("name")
            author_name = name_tag.get_text(strip=True) if name_tag else author.get_text(strip=True)
        description = item.find("description")
        keywords = item.find("media:keywords") or item.find("keywords")
        categories = [c.get_text(strip=True) for c in item.find_all("category")]
        content_encoded = item.find("content:encoded") or item.find("encoded")

        link_text = link.get_text(strip=True) if link and link.text else None
        section = None
        if link_text:
            path = link_text.replace("https://www.dn.pt/", "").split("?")[0]
            section = path.split("/", 1)[0] or None

        content_html = content_encoded.get_text() if content_encoded else None
        article_body = BeautifulSoup(content_html, "lxml").get_text("\n").strip() if content_html else None

        results.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.get_text(strip=True) if title and title.text else None,
                "link": link_text,
                "guid": guid.get_text(strip=True) if guid and guid.text else None,
                "pubDate": pub_date.get_text(strip=True) if pub_date and pub_date.text else None,
                "author": author_name,
                "description": description.get_text(strip=True) if description and description.text else None,
                "keywords": keywords.get_text(strip=True) if keywords and keywords.text else None,
                "categories": categories or None,
                "section": section,
                "articleBody": article_body,
            }
        )
    return results
