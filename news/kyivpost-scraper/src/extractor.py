"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html -- kyivpost.com emits 3 ld+json blocks per article page: a
             `NewsMediaOrganization` block, a `BreadcrumbList`, and a
             `NewsArticle` block -- the extractor scans all blocks and
             picks the one whose `@type` is `NewsArticle`. That block
             carries `headline`, `image`, `datePublished`, `dateModified`,
             `author` (a list of `Person` objects -- individual bylines,
             not agency-attributed), `publisher`, `isAccessibleForFree`,
             and `inLanguage` -- but **no `articleBody`** and no
             `description`. Full text is pulled from HTML instead: the
             article lives in `div#post-content > section.entry`, but a
             single article can be split across *multiple* sibling
             `section.entry` blocks (short news briefs interleave a
             `section.entry.telegram` widget-embed block between two
             `section.entry.text` blocks that hold the real paragraphs).
             Only *direct-child* `<p>`/`<h2>`/`<h3>` tags of each section
             are taken -- promo inserts ("JOIN US ON TELEGRAM" call-to-
             action, "Other Topics of Interest" related-post blocks, ad
             placeholders) are nested *inside* their own wrapper `<div>`
             siblings, not direct children, so they are excluded
             automatically without needing a denylist of classes.
             `description` is pulled from the `<meta name="description">`
             tag (confirmed present and populated on every sampled
             article). `category` is pulled from the `BreadcrumbList`
             block's second item (skipped, not raised on, if absent --
             it's a nice-to-have, not load-bearing).
  S2-rss  -- `/feed`, a WordPress-style RSS 2.0 feed (100 items, no
             pagination param found) with `title`/`link`/`description`
             (short teaser, not full article text)/`category`/`topic`
             (both repeatable)/`author`/`dc:creator`/`guid`/`pubDate`/
             `enclosure` (lead image).
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
    container = soup.select_one("div#post-content")
    if container is None:
        raise UnexpectedShape("No div#post-content element found -- page shape has likely changed.")
    sections = container.find_all("section", class_="entry")
    if not sections:
        raise UnexpectedShape("No section.entry element found inside div#post-content -- page shape has likely changed.")
    paragraphs = []
    for section in sections:
        for el in section.find_all(["p", "h2", "h3"], recursive=False):
            text = el.get_text(" ", strip=True)
            if text:
                paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _extract_category(soup: BeautifulSoup) -> str | None:
    breadcrumb = _find_ld_json_block(soup, "BreadcrumbList")
    if not breadcrumb:
        return None
    items = breadcrumb.get("itemListElement") or []
    if len(items) > 1 and isinstance(items[1], dict):
        return items[1].get("name")
    return None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article_body = _extract_body(soup)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    news_article = _find_ld_json_block(soup, "NewsArticle")
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    author = news_article.get("author") or []
    if isinstance(author, dict):
        author = [author]
    author_names = [a.get("name") for a in author if isinstance(a, dict) and a.get("name")]

    publisher = news_article.get("publisher") or {}

    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    description = meta_desc_tag.get("content") if meta_desc_tag else None

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "headline": news_article.get("headline"),
        "description": description,
        "articleBody": article_body,
        "author": ", ".join(author_names) if author_names else None,
        "publisher": publisher.get("name") if isinstance(publisher, dict) else publisher,
        "category": _extract_category(soup),
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "image": news_article.get("image"),
        "isAccessibleForFree": news_article.get("isAccessibleForFree"),
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
        topics = [t.text.strip() for t in item.find_all("topic") if t.text]
        creator = item.find("dc:creator") or item.find("author")
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
                "category": categories[0] if categories else None,
                "topics": topics or None,
                "author": creator.text.strip() if creator and creator.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "image": enclosure.get("url") if enclosure else None,
            }
        )
    return results
