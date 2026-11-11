"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html    -- koreaherald.com's `NewsArticle` ld+json block is minimal
               (`headline`, `image`, dates, `author`, `publisher` only --
               no `articleBody`, no `description`, no `keywords`). The
               extractor therefore takes metadata from **two sources**:
               `datePublished`/`dateModified`/`author`/`image` from
               ld+json, and `headline`/`description` re-derived from
               `<meta name="description">` (the ld+json `headline` has an
               unwanted `" - The Korea Herald"` site-name suffix baked in
               that the meta title does not carry as cleanly, so meta tags
               are preferred for both when present).
               Body text is scraped from the `<div itemprop="articleBody">`
               element (schema.org microdata attribute, found directly via
               attribute lookup -- no ld+json involved for this part) --
               every `<p>` tag inside it, dropping the empty
               `<p class="newline">` spacer tags the CMS inserts between
               paragraphs (these have zero text content, filtered by the
               same `if p.get_text(strip=True)` check used everywhere else
               in this portfolio).
  S2-sitemap -- rolling "latest articles" sitemap
               (`/sitemap/latest-articles`, advertised in robots.txt,
               ~73 entries, refreshed continuously) for `latest` mode.
               `news:title` is wrapped in `<![CDATA[...]]>` and is itself
               HTML-entity-escaped inside the CDATA block (e.g.
               `Kazakhstan&apos;s ruling party...`) -- entities inside
               CDATA are NOT XML-decoded by the parser (correct per spec,
               not a bug), so one manual `html.unescape()` pass is applied,
               same fix as `independent-scraper`'s `image:loc` quirk.
"""

import html
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


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


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article = _find_news_article(soup)
    if article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    body_el = soup.find(attrs={"itemprop": "articleBody"})
    if body_el is None:
        raise UnexpectedShape("No itemprop=articleBody element found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in body_el.find_all("p") if p.get_text(strip=True)]
    article_body = "\n\n".join(paragraphs)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    meta_title = soup.find("meta", attrs={"property": "og:title"})

    author = article.get("author")
    author_name = author.get("name") if isinstance(author, dict) else None

    image = article.get("image")
    image_url = image.get("url") if isinstance(image, dict) else (image if isinstance(image, str) else None)

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "headline": meta_title.get("content") if meta_title else article.get("headline"),
        "description": meta_desc.get("content") if meta_desc else None,
        "articleBody": article_body,
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "author": author_name,
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
        items.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                # news:title sits inside a CDATA block -- entities inside CDATA
                # are not XML-decoded by the parser, so a literal "&apos;" needs
                # one manual html.unescape() pass (same fix as
                # independent-scraper's image:loc quirk).
                "title": html.unescape(title.text.strip()) if title and title.text else None,
                "link": loc.text.strip() if loc and loc.text else None,
                "publicationDate": pub_date.text.strip() if pub_date and pub_date.text else None,
            }
        )
    return items
