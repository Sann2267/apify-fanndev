"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-microdata -- thehindu.com emits NO `application/ld+json` at all;
               structured data is schema.org **microdata**
               (`itemprop`/`itemscope` attributes on plain HTML tags)
               instead. `headline`/`datePublished`/`dateModified`/
               `articleSection`/`description` are `<meta itemprop="..."
               content="...">` tags. `itemprop="author"` is present but
               always an empty placeholder span in samples tested -- the
               real byline lives in a plain `.author-name` class element
               (falls back to that). Full text: `div[itemprop="articleBody"]
               > p` (bare paragraphs; "also read" inline-link boxes are
               separate `div.also-read` siblings, excluded by tag-name
               filtering).
  S2-rss    -- site-wide feed for `latest` mode. CDATA-wrapped fields
               throughout (title/description/link), handled transparently
               by the XML parser.
"""

from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _meta_itemprop(soup: BeautifulSoup, prop: str) -> str | None:
    el = soup.find("meta", attrs={"itemprop": prop})
    if el and el.get("content"):
        return el["content"].strip()
    return None


def extract_article(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    body_div = soup.select_one('div[itemprop="articleBody"]')
    if body_div is None:
        raise UnexpectedShape(
            'div[itemprop="articleBody"] not found -- page shape has likely changed.'
        )
    paragraphs = [
        p.get_text(" ", strip=True)
        for p in body_div.find_all("p")
        if p.get_text(strip=True)
    ]
    if not paragraphs:
        raise UnexpectedShape(
            "No body paragraphs extracted from articleBody div -- page shape "
            "has likely changed."
        )
    article_body = "\n\n".join(paragraphs)

    headline = _meta_itemprop(soup, "headline")
    if headline is None:
        raise UnexpectedShape(
            'meta[itemprop="headline"] not found -- page shape has likely changed.'
        )

    author_el = soup.select_one(".author-name")

    return {
        "_input": url,
        "_source": "S1-microdata",
        "_scrapedAt": utc_now_iso(),
        "headline": headline,
        "description": _meta_itemprop(soup, "description"),
        "articleBody": article_body,
        "articleSection": _meta_itemprop(soup, "articleSection"),
        "datePublished": _meta_itemprop(soup, "datePublished"),
        "dateModified": _meta_itemprop(soup, "dateModified"),
        "author": author_el.get_text(strip=True) if author_el else None,
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
    items = []
    for item in soup.find_all("item"):
        title = item.find("title")
        link = item.find("link")
        guid = item.find("guid")
        pub_date = item.find("pubDate")
        description = item.find("description")
        categories = [c.text.strip() for c in item.find_all("category") if c.text]
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title else None,
                "link": link.text.strip() if link else None,
                "guid": guid.text.strip() if guid else None,
                "pubDate": pub_date.text.strip() if pub_date else None,
                "description": description.text.strip() if description else None,
                "categories": categories,
            }
        )
    return items
