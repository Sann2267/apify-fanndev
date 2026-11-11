"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html          -- jamaica-gleaner.com emits a single ld+json block
                      typed `Article` with `headline`, `image`,
                      `datePublished`, `dateModified`, and
                      `isAccessibleForFree` -- but no `articleBody`,
                      `description`, or `author`. Full text comes from
                      HTML `div.article--body > p` (plain unwrapped `<p>`
                      tags, confirmed clean on 2 samples -- no ad/related-
                      article junk paragraphs mixed in; the last paragraph
                      is sometimes a reporter's byline email, e.g.
                      "neville.graham@gleanerjm.com", which is left in as
                      real editorial content per raw-passthrough
                      convention, not stripped). `postedDate` (a readable
                      but non-ISO string like "August 23 2026") is pulled
                      separately from `.article--posted-date` as a
                      secondary/redundant date field alongside the ld+json
                      `datePublished` (which is a proper ISO timestamp and
                      should be preferred by consumers).
  S2-html-listing  -- both of the site's normal discovery mechanisms are
                      broken: `sitemap.xml` returns 404, and `rss.xml`
                      returns HTTP 200 but is a genuinely empty stub (a
                      `<channel>` with zero `<item>` elements) -- confirmed
                      on this pass, matching prior recon-session notes.
                      Instead the homepage is scraped for `<a href>` links
                      matching `/article/<section>/<YYYYMMDD>/<slug>`.
                      Because the date is embedded in the URL itself,
                      sorting descending by that date component reproduces
                      newest-first order without visiting each article.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

ARTICLE_URL_RE = re.compile(r"/article/([a-z\-]+)/(\d{8})/([a-z0-9\-]+)")


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_article(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("@type") == "Article":
            return data
    return None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    body_el = soup.select_one("div.article--body")
    if body_el is None:
        raise UnexpectedShape("No div.article--body element found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in body_el.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    article_body = "\n\n".join(paragraphs)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    article = _find_article(soup)
    if article is None:
        raise UnexpectedShape("No Article ld+json block found -- page shape has likely changed.")

    title_el = soup.select_one(".article--title")
    posted_el = soup.select_one(".article--posted-date")
    is_free = article.get("isAccessibleForFree")

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "headline": title_el.get_text(strip=True) if title_el else article.get("headline"),
        "articleBody": article_body,
        "postedDate": posted_el.get_text(" ", strip=True) if posted_el else None,
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "image": article.get("image"),
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


def _normalize_url(href: str) -> str:
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return "https://jamaica-gleaner.com" + href
    return href


def extract_latest_items(html_text: str) -> list[dict]:
    soup = BeautifulSoup(html_text, "lxml")

    titles: dict[str, str] = {}
    order: list[str] = []
    sections: dict[str, str] = {}
    dates: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = ARTICLE_URL_RE.search(href)
        if not m:
            continue
        norm = _normalize_url(href)
        text = a.get_text(strip=True)
        if norm not in titles:
            order.append(norm)
            titles[norm] = ""
            sections[norm] = m.group(1)
            dates[norm] = m.group(2)
        if text and len(text) > len(titles[norm]):
            titles[norm] = text

    order.sort(key=lambda link: dates[link], reverse=True)

    items = []
    for link in order:
        raw_date = dates[link]
        items.append(
            {
                "_input": "latest",
                "_source": "S2-html-listing",
                "_scrapedAt": utc_now_iso(),
                "title": titles[link] or None,
                "link": link,
                "section": sections[link],
                # Day precision only -- derived from the URL path, not a
                # true publish timestamp. Fetch the article (article mode)
                # for the exact `datePublished` from its ld+json block.
                "urlDate": f"{raw_date[0:4]}-{raw_date[4:6]}-{raw_date[6:8]}",
            }
        )
    return items
