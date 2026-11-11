"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-nextdata -- `__NEXT_DATA__` script tag, `props.pageProps.globalContent`.
                 This is the raw Arc Publishing ANS (Arc News Story) object --
                 the richest available shape (byline bios, taxonomy/tags,
                 kicker, teaser content_elements, images, related_content).
  S2-jsonld   -- `application/ld+json` NewsArticle block. Used only if the
                 __NEXT_DATA__ script tag is missing (Next.js build change) --
                 per project convention JSON-LD is the more stable layer, but
                 it carries strictly fewer fields, so it's the fallback here
                 rather than the primary.
  S3-rss      -- for `latest` mode: RSS <item> (title/link/creator/pubDate/
                 description only -- no body).

Washington Post enforces a metered paywall server-side: `globalContent` is
present for every article, but `content_elements` is truncated to a short
teaser (a couple of paragraphs) when `restricted: true`. That's raw-passthrough
verbatim -- this actor does not attempt to defeat the paywall.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_next_data_global_content(html: str) -> dict | None:
    m = NEXT_DATA_RE.search(html)
    if not m:
        return None
    try:
        nd = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise UnexpectedShape(f"__NEXT_DATA__ present but not valid JSON: {e}") from e
    page_props = nd.get("props", {}).get("pageProps", {})
    global_content = page_props.get("globalContent")
    if not global_content:
        return None
    if "_id" not in global_content or "content_elements" not in global_content:
        raise UnexpectedShape(
            f"globalContent missing expected keys; got={list(global_content.keys())}"
        )
    return global_content


def _extract_json_ld_article(html: str) -> dict | None:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not tag.string:
            continue
        try:
            data = json.loads(tag.string)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") in (
            "NewsArticle",
            "ReportageNewsArticle",
            "Article",
        ):
            return data
    return None


def extract_article(html: str, url: str) -> dict:
    """raw is upstream payload (passthrough); returns dataset-ready record."""
    global_content = _extract_next_data_global_content(html)
    if global_content is not None:
        return {
            "_input": url,
            "_source": "S1-nextdata",
            "_scrapedAt": utc_now_iso(),
            **global_content,
        }

    article = _extract_json_ld_article(html)
    if article is not None:
        return {
            "_input": url,
            "_source": "S2-jsonld",
            "_scrapedAt": utc_now_iso(),
            **article,
        }

    raise UnexpectedShape(
        "Neither __NEXT_DATA__.props.pageProps.globalContent nor a NewsArticle "
        "ld+json block was found -- page shape has likely changed."
    )


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_rss_items(xml_bytes: bytes, section: str) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    items = []
    for item in soup.find_all("item"):
        link = item.find("link")
        guid = item.find("guid")
        creator = item.find("dc:creator")
        pub_date = item.find("pubDate")
        description = item.find("description")
        title = item.find("title")
        url = (link.text if link else guid.text if guid else "").strip()
        items.append(
            {
                "_input": f"latest:{section}",
                "_source": "S3-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title else None,
                "link": url,
                "guid": guid.text.strip() if guid else None,
                "creator": creator.text.strip() if creator else None,
                "pubDate": pub_date.text.strip() if pub_date else None,
                "description": description.text.strip() if description else None,
                "section": section,
            }
        )
    return items
