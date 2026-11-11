"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- mmegi.bw article pages (all 3 sampled sections: news, sports,
               opinion-amp-analysis) emit exactly ONE top-level (non-`@graph`)
               `NewsArticle` ld+json node that carries **`articleBody` with
               the FULL article text inline** -- no HTML scraping needed.
               Also present: `headline`, `description`, `keywords` (a
               comma-separated string, oddly just the headline's words
               re-joined with commas rather than real topical keywords --
               kept as a split list, raw passthrough style), `inLanguage`,
               `thumbnailUrl`, `image` (a single `ImageObject` dict, not a
               list), `author` (a single `Person` dict -- `{"name":
               "correspondent"}` / `"staff writer"` for unbylined wire-style
               pieces, a real reporter name e.g. `"REALEBOGA PHOI"` for
               opinion pieces), `publisher` and `copyrightHolder` (both
               `Organization` dicts), `dateCreated`/`datePublished`/
               `dateModified`, and `mainEntityOfPage` (`{"@type": "WebPage",
               "@id": <canonical url>}`).
               **No paywall metadata was found anywhere** -- no
               `isAccessibleForFree`, no `hasPart` -- unlike
               `standardmedia-scraper`'s Piano-style flags; Mmegi's online
               articles appear to be fully open, matching the fact that no
               login/subscription wall was ever hit while sampling.
               **Key quirk (single HTML-entity escaping):** `articleBody`
               (and `title`/`description` on the RSS feed, see S2 below) is
               single html-entity-escaped on the wire -- e.g. a literal
               double-quote is served as the literal 4-character sequence
               `&quot;` inside the JSON string. One `html.unescape()` pass
               recovers the real character; verified this is idempotent (a
               second pass is a no-op) so `_clean_text()` is safe to reuse
               everywhere text might carry entities. Unlike
               `standardmedia-scraper`, this is NOT double-escaped, and
               standard `json.loads()` (strict mode) parses every sampled
               article cleanly -- no stray unescaped control characters were
               found on the wire here.
  S2-rss    -- Per-category RSS feeds at `/rssFeed/<id>` (News=1,
               Business=2, Sports=3, Features=4, Opinion & Analysis=13,
               Blogs=24, Lifestyle=25, ...), discovered via the human-
               readable `/rss` sitemap page (not advertised in robots.txt --
               this site has no `sitemap:` line there at all). This actor
               uses the News feed (id=1) as the `latest`-mode source.
               Standard RSS 2.0 shape, all fields CDATA-wrapped: `title`,
               `link`, `description` (a short teaser, same single-escaping
               quirk as articleBody), `author` (plain name, not an email --
               same values as the ld+json `author.name`), `pubDate`
               (RFC-822), plus `media:thumbnail`/`media:content` (both carry
               the same image URL at different declared sizes -- thumbnail
               400x280, content 800x557 in samples -- both kept). No
               `guid` or `category` element is present on this feed.
"""

import html
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_text(raw: str | None) -> str | None:
    # See module docstring -- single html-entity-escaped on the wire.
    # html.unescape() is idempotent for already-clean text, safe to always apply.
    if raw is None:
        return None
    return html.unescape(raw).strip()


def _find_news_article(soup: BeautifulSoup) -> dict | None:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "NewsArticle":
            return data
    return None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article = _find_news_article(soup)
    if article is None:
        raise UnexpectedShape("No NewsArticle ld+json node found -- page shape has likely changed.")

    article_body = _clean_text(article.get("articleBody"))
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    author = article.get("author")
    author_name = author.get("name") if isinstance(author, dict) else author

    keywords = article.get("keywords")
    keywords_list = (
        [_clean_text(k.strip()) for k in keywords.split(",") if k.strip()]
        if isinstance(keywords, str)
        else keywords
    )

    image = article.get("image")
    image_url = image.get("url") if isinstance(image, dict) else image

    main_entity = article.get("mainEntityOfPage")
    canonical_url = main_entity.get("@id") if isinstance(main_entity, dict) else None

    return {
        "_input": url,
        "_source": "S1-jsonld",
        "_scrapedAt": utc_now_iso(),
        "headline": _clean_text(article.get("headline")),
        "description": _clean_text(article.get("description")),
        "articleBody": article_body,
        "keywords": keywords_list,
        "inLanguage": article.get("inLanguage"),
        "author": author_name,
        "dateCreated": article.get("dateCreated"),
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "thumbnailUrl": article.get("thumbnailUrl"),
        "image": image_url,
        "publisher": article.get("publisher"),
        "copyrightHolder": article.get("copyrightHolder"),
        "canonicalUrl": canonical_url,
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
    items = soup.find_all("item")
    if not items:
        raise UnexpectedShape("No <item> elements found in RSS feed -- feed shape has likely changed.")

    results = []
    for item in items:
        title = item.find("title")
        link = item.find("link")
        description = item.find("description")
        author = item.find("author")
        pub_date = item.find("pubDate")
        thumbnail = item.find("media:thumbnail")
        content = item.find("media:content")
        results.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": _clean_text(title.text) if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "description": _clean_text(description.text) if description and description.text else None,
                "author": author.text.strip() if author and author.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "thumbnailUrl": thumbnail.get("url") if thumbnail else None,
                "imageUrl": content.get("url") if content else None,
            }
        )
    return results
