"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html -- telegraph.co.uk emits exactly ONE `application/ld+json`
             block per article page (`@type: NewsArticle`) -- no
             `BreadcrumbList`, no separate `NewsMediaOrganization`
             block like most of the rest of this portfolio. It carries
             `headline`, `url`, `datePublished`, `dateModified`,
             `inLanguage`, `articleSection` (confirmed **always empty
             string** on every sample), `keywords` (comma-separated tag
             string -- always populated, doubles as a category proxy),
             `publisher`, `isAccessibleForFree` (**always `true`** on
             every one of 13 sampled articles, including a flagship
             Ambrose Evans-Pritchard economics column), `author` (list
             of `Person` objects), and `image` -- but **no
             `articleBody`** at all (not truncated -- the key is simply
             absent from the JSON).
             Full text is pulled from HTML instead: the article body is
             split across **multiple sibling `div.articleBodyText`**
             blocks, interleaved with `figure.article-body-image`
             blocks (each new body paragraph-group follows a new inline
             image/caption). The first `div.articleBodyText` wraps an
             inner `div.component.article-body-text` (carries the
             `data-test="article-body-text"` marker); later sibling
             `div.articleBodyText` blocks hold `<p>` tags directly, no
             inner wrapper. `find_all("p")` recursively inside every
             `div.articleBodyText` collects the complete body regardless
             of which shape a given block uses.
  S2-rss  -- `/rss.xml`, the sitewide latest-news feed, with
             `title`/`link`/`description`/`pubDate`/`guid`/
             `dc:creator` (repeatable -- multiple bylines)/`category`
             (repeatable, taxonomy-style values like
             `topics:places/middle-east`, `structure:opinion`,
             `storytype:comment`)/`enclosure` (lead image).
"""

import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    blocks = soup.find_all("div", class_="articleBodyText")
    if not blocks:
        raise UnexpectedShape("No div.articleBodyText element found -- page shape has likely changed.")
    paragraphs = []
    for block in blocks:
        for p in block.find_all("p"):
            text = p.get_text(" ", strip=True)
            if text:
                paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _section_from_url(url: str) -> str | None:
    # Best-effort, not load-bearing: telegraph.co.uk ld+json has no
    # BreadcrumbList, so the first URL path segment is the closest
    # stand-in for a section/category (e.g. "news", "business", "sport").
    try:
        path = url.split("://", 1)[1].split("/", 1)[1]
        segment = path.split("/", 1)[0]
        return segment or None
    except IndexError:
        return None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    news_article = _find_ld_json_block(soup, "NewsArticle")
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    article_body = _extract_body(soup)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    author = news_article.get("author") or []
    if isinstance(author, dict):
        author = [author]
    author_names = [a.get("name") for a in author if isinstance(a, dict) and a.get("name")]

    publisher = news_article.get("publisher") or {}
    is_free = news_article.get("isAccessibleForFree")

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "headline": news_article.get("headline"),
        "articleBody": article_body,
        "author": ", ".join(author_names) if author_names else None,
        "publisher": publisher.get("name") if isinstance(publisher, dict) else publisher,
        "section": _section_from_url(url),
        "keywords": news_article.get("keywords"),
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "image": news_article.get("image"),
        "isAccessibleForFree": is_free,
        # Honest per-article flag, never fabricated: True only when upstream
        # explicitly said the article is NOT free AND the body we scraped
        # looks like a stub. Every article sampled during recon (including
        # a flagship Ambrose Evans-Pritchard column) had isAccessibleForFree
        # == true and a full-length body, so this has never fired in
        # practice -- see CRAWLING_METHOD.md "Paywall behavior".
        "_paywalled": bool(is_free is False and len(article_body) < 600),
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
    items = soup.find_all("item")
    if not items:
        raise UnexpectedShape("No <item> elements found in RSS feed -- feed shape has likely changed.")
    results = []
    for item in items:
        title = item.find("title")
        link = item.find("link")
        description = item.find("description")
        pub_date = item.find("pubDate")
        categories = [c.text.strip() for c in item.find_all("category") if c.text]
        creators = [c.text.strip() for c in item.find_all("dc:creator") if c.text]
        guid = item.find("guid")
        enclosure = item.find("enclosure")
        results.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "description": description.text.strip() if description and description.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "categories": categories or None,
                "author": ", ".join(creators) if creators else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "image": enclosure.get("url") if enclosure else None,
            }
        )
    return results
