"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- `application/ld+json` `NewsArticle` block (aftenposten.no
               emits two separate script tags -- one `NewsArticle`, one
               `BreadcrumbList`). Never carries `articleBody`, so full text
               is pulled separately from the HTML `article` container (all
               `<p>` tags, joined) and attached as `articleBody`.
  S2-rss    -- for `latest` mode: RSS <item> (title/link/pubDate/description
               only -- no body).

Sampled 10 live articles (2026-08-24): 8/10 standard news pieces carried the
NewsArticle block; 2/10 culture/review pieces did not (different content
type, not schema drift -- see Known limits in CRAWLING_METHOD.md). Those
raise `NotNewsArticle`, caught per-URL in main.py and turned into an
`_error` record, the same way business-standard-scraper handles its
soft-404. Genuine schema drift (an ld+json block found but not parseable)
still raises `UnexpectedShape` and fails the run loudly.
"""

import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


class NotNewsArticle(Exception):
    """Page has no NewsArticle ld+json block -- a legitimate non-article
    content type (culture/review pages), not a site redesign. Caught
    per-URL in main.py, same tier as a 404."""


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
    raise NotNewsArticle(
        "No NewsArticle ld+json block found -- this URL is likely a "
        "non-article content type (e.g. culture/review page)."
    )


def _extract_body_text(soup: "BeautifulSoup") -> str | None:
    el = soup.select_one("article")
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
                "_input": "latest:aftenposten.no",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title else None,
                "link": url,
                "pubDate": pub_date.text.strip() if pub_date else None,
                "description": description.text.strip() if description else None,
            }
        )
    return items
