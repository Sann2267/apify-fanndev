"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html    -- jpost.com emits 5 ld+json blocks per article page
               (`WebSite`, `NewsMediaOrganization`, `NewsArticle`,
               `BreadcrumbList`, and one untyped block) -- the extractor
               scans all blocks and picks the one whose `@type` is
               `NewsArticle`. Unlike most sibling actors, that block
               carries **full `articleBody` inline** -- no HTML fallback
               selector needed. Also carries `headline`, `description`,
               `datePublished`, `dateModified`, `author` (a *list* of
               `Person` objects -- individual bylines, not agency-
               attributed), `publisher` (`NewsMediaOrganization`),
               `image`, `articleSection`, `keywords`, and
               `isAccessibleForFree` (a genuine paywall flag -- 13 diverse
               articles sampled during recon across sections
               [israel-news, opinion, sports, defense-and-tech,
               archaeology, history, travel, food-recipes, omg,
               mdaheroes, american-politics] were all `true`; no
               paywalled sample was found, but the flag is honored
               defensively rather than assumed).
  S2-sitemap -- Google News sitemap
               (`/GoogleNewsSiteMap/GNSiteMap`), ~300 recent articles,
               carries `loc`/`lastmod`/`news:title`/
               `news:publication_date`/`news:keywords` inline -- no
               per-article fetch needed for `latest` mode.
"""

import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


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


def _author_names(author) -> list | str | None:
    if isinstance(author, list):
        names = [a.get("name") for a in author if isinstance(a, dict) and a.get("name")]
        return names or None
    if isinstance(author, dict):
        return author.get("name")
    return author


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    news_article = _find_news_article(soup)
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    if "articleBody" not in news_article:
        raise UnexpectedShape("NewsArticle ld+json has no articleBody key -- page shape has likely changed.")

    article_body = news_article.get("articleBody") or ""
    is_free = news_article.get("isAccessibleForFree")
    paywalled = is_free is False

    # A genuinely open article with an empty body is schema drift, not a
    # paywall -- raise loud. A paywalled article with a short/empty body
    # is expected paywall degradation -- flag it, don't crash the run.
    if not article_body and not paywalled:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    publisher = news_article.get("publisher") or {}

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "_paywalled": paywalled,
        "headline": news_article.get("headline"),
        "description": news_article.get("description"),
        "articleBody": article_body,
        "author": _author_names(news_article.get("author")),
        "publisher": publisher.get("name") if isinstance(publisher, dict) else publisher,
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "articleSection": news_article.get("articleSection"),
        "keywords": news_article.get("keywords"),
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


def extract_sitemap_items(xml_text: str) -> list[dict]:
    soup = BeautifulSoup(xml_text, "xml")
    urls = soup.find_all("url")
    if not urls:
        raise UnexpectedShape("Google News sitemap has no <url> entries -- feed shape has likely changed.")

    items = []
    for u in urls:
        loc = u.find("loc")
        lastmod = u.find("lastmod")
        title = u.find("news:title") or u.find("title")
        pub_date = u.find("news:publication_date") or u.find("publication_date")
        keywords = u.find("news:keywords") or u.find("keywords")
        keyword_list = None
        if keywords and keywords.text:
            keyword_list = [k.strip() for k in keywords.text.split(",") if k.strip()]
        items.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": loc.text.strip() if loc and loc.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "lastmod": lastmod.text.strip() if lastmod and lastmod.text else None,
                "keywords": keyword_list,
            }
        )
    return items
