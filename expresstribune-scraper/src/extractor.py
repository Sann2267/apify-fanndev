"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html   -- tribune.com.pk emits a single `NewsArticle` ld+json block
               (headline, dates, description, image, author, publisher --
               but NO `articleBody`). Two different CMS body templates were
               found across samples: hard-news/business articles use
               `div.express-parent-div`, while long-form opinion/fiction
               pieces use `div.custom-row` instead (no shared class between
               them) -- the extractor tries `express-parent-div` first,
               falls back to `custom-row`, and raises `UnexpectedShape` if
               neither is present. Trailing boilerplate paragraphs
               (comment-section prompts, copyright notice) are filtered by
               exact-match/prefix; inline "Read More: ..." related-article
               link paragraphs are filtered by prefix too.
  S2-sitemap -- `/sitemap/latest-1.xml` (advertised via `Sitemap:` in
               robots.txt), a plain XML sitemap (loc/lastmod/changefreq/
               priority only -- no `news:title`), already newest-first.
               Since there's no title field, a readable title is derived
               from the URL slug (last path segment, hyphens -> spaces,
               title-cased) -- cosmetic only, not a substitute for the
               real `headline` you get from `article` mode.

WAF quirk: a nonexistent `/story/<id>/...` URL triggers a Cloudflare
challenge (see client.py/constants.py) rather than a clean 404 -- treated
upstream (main.py) as `blocked_or_transient`, not `not_found`.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

BOILERPLATE_EXACT = {
    "COMMENTS",
}
BOILERPLATE_PREFIXES = (
    "Comments are moderated and generally will be posted",
    "For more information, please see our Comments FAQ",
    "This material may not be published, broadcast, rewritten,",
    "Read More:",
)

_SLUG_RE = re.compile(r"/story/\d+/([^/]+)/?$")


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_news_article(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and data.get("@type") == "NewsArticle":
            return data
    return None


def _find_body_container(soup: BeautifulSoup):
    el = soup.select_one("div.express-parent-div")
    if el is not None:
        return el, "express-parent-div"
    el = soup.select_one("div.custom-row")
    if el is not None:
        return el, "custom-row"
    return None, None


def _is_boilerplate(text: str) -> bool:
    if text in BOILERPLATE_EXACT:
        return True
    return any(text.startswith(p) for p in BOILERPLATE_PREFIXES)


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    body_el, template = _find_body_container(soup)
    if body_el is None:
        raise UnexpectedShape(
            "Neither div.express-parent-div nor div.custom-row found -- page shape has likely changed."
        )
    paragraphs = [p.get_text(" ", strip=True) for p in body_el.find_all("p")]
    paragraphs = [p for p in paragraphs if p and not _is_boilerplate(p)]
    article_body = "\n\n".join(paragraphs)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    news_article = _find_news_article(soup)
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    author = news_article.get("author") or {}
    publisher = news_article.get("publisher") or {}

    return {
        "_input": url,
        "_source": f"S1-html[{template}]",
        "_scrapedAt": utc_now_iso(),
        "headline": news_article.get("headline"),
        "description": news_article.get("description"),
        "articleBody": article_body,
        "author": author.get("name") if isinstance(author, dict) else author,
        "publisher": publisher.get("name") if isinstance(publisher, dict) else publisher,
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "image": news_article.get("image"),
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def _title_from_slug(link: str) -> str | None:
    m = _SLUG_RE.search(link)
    if not m:
        return None
    slug = m.group(1)
    return slug.replace("-", " ").strip().title() or None


def extract_sitemap_items(xml_text: str) -> list[dict]:
    soup = BeautifulSoup(xml_text, "xml")
    items = []
    for url_tag in soup.find_all("url"):
        loc = url_tag.find("loc")
        lastmod = url_tag.find("lastmod")
        if loc is None or not loc.text:
            continue
        link = loc.text.strip()
        items.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": _title_from_slug(link),
                "link": link,
                "lastmod": lastmod.text.strip() if lastmod and lastmod.text else None,
            }
        )
    return items
