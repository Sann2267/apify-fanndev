"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- `application/ld+json` `NewsArticle` block (aftonbladet.se
               emits two separate script tags -- one `BreadcrumbList`, one
               `NewsArticle` -- the extractor scans all of them and picks
               the `NewsArticle` one). Never carries `articleBody`, so full
               text is pulled separately from the HTML `main article`
               container (all `<p>` tags, joined) and attached as
               `articleBody`. Verified against the ld+json `wordCount`
               field on 10 live samples -- no truncation found.
  S2-rss    -- for `latest` mode: RSS <item> (title/link/pubDate/description
               only -- no body).
"""

import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_json_ld_article(html_bytes: bytes) -> tuple[dict, "BeautifulSoup"]:
    soup = BeautifulSoup(html_bytes, "lxml")
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not tag.string:
            continue
        try:
            data = json.loads(tag.string)
        except json.JSONDecodeError:
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") == "NewsArticle":
                return item, soup
    raise UnexpectedShape(
        "No NewsArticle ld+json block found -- page shape has likely changed."
    )


def _extract_body_text(soup: "BeautifulSoup") -> str | None:
    el = soup.select_one("main article") or soup.select_one("article")
    if el is None:
        return None
    paras = el.find_all("p")
    if paras:
        text = "\n\n".join(p.get_text(strip=True) for p in paras if p.get_text(strip=True))
    else:
        text = el.get_text(separator="\n\n", strip=True)
    return text or None


def extract_article(html_bytes: bytes, url: str) -> dict:
    """raw is upstream payload (passthrough); returns dataset-ready record."""
    article, soup = _extract_json_ld_article(html_bytes)
    body_text = _extract_body_text(soup)
    is_free = article.get("isAccessibleForFree")

    return {
        "_input": url,
        "_source": "S1-jsonld",
        "_scrapedAt": utc_now_iso(),
        "_paywalled": (is_free is False),
        **article,
        "articleBody": body_text,
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_rss_items(xml_bytes: bytes, limit: int) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    items = []
    for item in soup.find_all("item")[:limit]:
        link = item.find("link")
        pub_date = item.find("pubDate")
        description = item.find("description")
        title = item.find("title")
        url = link.text.strip() if link else ""
        items.append(
            {
                "_input": "latest:aftonbladet.se",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title else None,
                "link": url,
                "pubDate": pub_date.text.strip() if pub_date else None,
                "description": description.text.strip() if description else None,
            }
        )
    return items
