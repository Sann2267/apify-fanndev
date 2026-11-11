"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html   -- JSON-LD `NewsArticle` block on the article page supplies
               headline/author/creator/dates/section/keywords/image/
               `isAccessibleForFree`, but no `articleBody`. Full text comes
               from `div.article-body > div.body-copy > p` (bare `<p>`
               tags, no class -- ad slots and the audio-player widget are
               separate sibling divs, excluded by tag-name filtering).
               `isAccessibleForFree` is consistently `false` in the JSON-LD
               even on articles with full text present in the HTML (a
               metering flag, not a server-side truncation -- same pattern
               documented for latimes-scraper).
  S2-homepage -- `latest` mode has NO working feed (see constants.py for
               why) -- headlines are scraped from the homepage instead:
               every `<a href="https://www.chicagotribune.com/YYYY/MM/DD/...">`
               with a `title` attribute is a headline; `title` is the
               headline text (the `<a>` itself wraps only a thumbnail
               image, no visible text). This is "current homepage top
               stories," not a true reverse-chronological feed -- older
               evergreen columns (e.g. daily trivia/advice columns) can
               appear alongside same-day news.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

JSON_LD_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I
)

ARTICLE_TYPES = {"NewsArticle", "ReportageNewsArticle", "Article"}

HOMEPAGE_LINK_RE = re.compile(r"^https://www\.chicagotribune\.com/\d{4}/\d{2}/\d{2}/")


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_article_jsonld(html: str) -> dict | None:
    for match in JSON_LD_RE.finditer(html):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") in ARTICLE_TYPES:
            return data
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") in ARTICLE_TYPES:
                    return item
    return None


def _extract_body_text(soup: BeautifulSoup) -> str:
    body_copy = soup.select_one("div.article-body div.body-copy")
    if body_copy is None:
        raise UnexpectedShape(
            "div.article-body > div.body-copy not found -- page shape has likely changed."
        )
    paragraphs = [
        p.get_text(" ", strip=True)
        for p in body_copy.find_all("p", recursive=False)
        if p.get_text(strip=True)
    ]
    if not paragraphs:
        raise UnexpectedShape(
            "No body paragraphs extracted from body-copy -- page shape has likely changed."
        )
    return "\n\n".join(paragraphs)


def extract_article(html: str, url: str) -> dict:
    data = _find_article_jsonld(html)
    if data is None:
        raise UnexpectedShape(
            "No NewsArticle ld+json block found -- page shape has likely changed."
        )
    soup = BeautifulSoup(html, "lxml")
    article_body = _extract_body_text(soup)
    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        **data,
        "articleBody": article_body,
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_homepage_headlines(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    seen = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0]
        title = a.get("title")
        if title and HOMEPAGE_LINK_RE.match(href) and href not in seen:
            seen[href] = title.strip()
    return [
        {
            "_input": "latest",
            "_source": "S2-homepage",
            "_scrapedAt": utc_now_iso(),
            "title": title,
            "link": href,
        }
        for href, title in seen.items()
    ]
