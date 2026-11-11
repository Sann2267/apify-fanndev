"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-meta+html -- 24.kg does NOT emit a JSON-LD `NewsArticle` block (the
             only `<script type="application/ld+json">` on an article page
             is a `BreadcrumbList`). The site instead marks up the article
             with schema.org **microdata** (`itemscope
             itemtype="http://schema.org/NewsArticle"`, `itemprop="..."`
             attributes inline in the HTML) -- one layer down the
             stability ladder from JSON-LD but still structured, not raw
             CSS scraping.

             The microdata's own `datePublished`/`dateModified` attribute
             values carry a genuine site bug: a stray literal backslash
             before the closing quote (e.g. `content='2026-08-26\'`), and
             the visible `datePublished` only carries a date, not a
             timestamp (the time is in adjacent human-readable text, not
             a machine-readable attribute). The OpenGraph/`article:*` meta
             tags (`article:published_time`, `article:modified_time`) are
             clean full ISO 8601 timestamps with timezone offset and are
             used instead for dates; the microdata is only relied on for
             `headline` (meta) and to positively confirm the page is an
             article (`itemtype="http://schema.org/NewsArticle"`).

             Full body text comes from `div.cont[itemprop="articleBody"]`,
             direct `<p dir="ltr">` tags.

             `<meta name="author">` is present on Russian-language,
             byline-carrying articles but is genuinely absent (no tag at
             all, not an empty one) on some articles, notably observed on
             a Kyrgyz-language (`/kyrgyzcha/`) sample -- treated as
             optional, not a shape error.

             The site is bilingual Russian/Kyrgyz: most sections are
             Russian, `/kyrgyzcha/` is Kyrgyz. `<html lang="...">` is the
             reliable per-article language signal (`ru-RU` vs `ky-KG`);
             the `og:locale` meta tag is a site bug -- it is hardcoded
             `ru_ru` even on Kyrgyz-language pages, so it is NOT used.
             `_lang` in the output is read from `<html lang>`, not
             `og:locale`.

             A non-article page (e.g. a category listing like
             `/ekonomika/`) carries neither the `NewsArticle` itemtype nor
             the `articleBody` div -- detected explicitly and reported as
             `_error: "not_article"` rather than raising.
  S2-rss   -- `/rss/`, a plain RSS 2.0 feed, ~50 items, newest-first,
             refreshed continuously (`ttl` 10 minutes). Teaser-only:
             `title`, `link`, `description`, `category`, `pubDate`, `guid`
             -- no embedded full body text (unlike Kazinform's feed.xml).
"""

import html
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


class ArticleNotFound(Exception):
    """A 200-OK page that isn't an article (e.g. a category listing)."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_text(text: str | None) -> str | None:
    """Normalize whitespace and unescape HTML entities.

    The site's RSS feed (`/rss/`) embeds titles/descriptions inside
    `<![CDATA[...]]>` blocks that themselves contain literal HTML-entity
    syntax (e.g. `В&nbsp;городе`) -- a genuine double-encoding quirk. XML
    entities are not expanded inside CDATA per spec, so BeautifulSoup's XML
    parser correctly leaves them as literal `&nbsp;`/`&laquo;`/`&raquo;`
    text. `html.unescape()` cleans that up; it's a no-op on the HTML-mode
    text (already decoded by the lxml HTML parser), so it's safe to apply
    unconditionally here.
    """
    if not text:
        return None
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _meta_content(soup: BeautifulSoup, **attrs) -> str | None:
    tag = soup.find("meta", attrs=attrs)
    if tag is None:
        return None
    return _clean_text(tag.get("content"))


def _paragraphs_to_text(container) -> str:
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    return "\n\n".join(paragraphs)


def _news_article_ld(soup: BeautifulSoup) -> dict | None:
    """The `NewsArticle` JSON-LD block the 2026 Next.js redesign emits."""
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (ValueError, TypeError):
            continue
        for node in data if isinstance(data, list) else [data]:
            if isinstance(node, dict) and node.get("@type") == "NewsArticle":
                return node
    return None


def _ld_authors(ld: dict) -> str | None:
    authors = ld.get("author")
    if isinstance(authors, dict):
        authors = [authors]
    if not isinstance(authors, list):
        return None
    names = [a.get("name") for a in authors if isinstance(a, dict) and a.get("name")]
    return _clean_text(", ".join(names))


def _ld_image(ld: dict) -> str | None:
    image = ld.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        image = image.get("url")
    return image or None


def _section_from_url(url: str) -> str | None:
    """First path segment, e.g. `/proisshestvija/<slug>/` -> `proisshestvija`.
    The redesign dropped the `article:section` meta tag."""
    parts = [p for p in urlparse(url).path.split("/") if p]
    return parts[0] if len(parts) >= 2 else None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    # Since the 2026 redesign (Next.js) the page carries a JSON-LD
    # `NewsArticle` and the body sits in `div.article-viewer-content.cont`;
    # the old microdata (`itemprop="articleBody"`) is gone. Both layouts are
    # accepted so a rollback does not break the actor again.
    ld = _news_article_ld(soup)
    is_news_article = ld is not None or soup.find(
        attrs={"itemtype": "http://schema.org/NewsArticle"}) is not None
    body_el = (soup.select_one("div.article-viewer-content")
               or soup.select_one('div.cont[itemprop="articleBody"]'))

    if not is_news_article and body_el is None:
        raise ArticleNotFound("No NewsArticle JSON-LD/microdata and no article body -- not an article page.")

    if body_el is None:
        raise UnexpectedShape("NewsArticle present but no article body container found.")

    article_body = _paragraphs_to_text(body_el)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    ld = ld or {}
    headline = _clean_text(ld.get("headline")) or _meta_content(soup, itemprop="headline")
    if not headline:
        h1 = soup.select_one("h1")
        headline = _clean_text(h1.get_text(" ", strip=True)) if h1 else None
    if not headline:
        raise UnexpectedShape("No headline found (JSON-LD, meta[itemprop=headline] and h1 all missing).")

    html_tag = soup.find("html")
    lang = html_tag.get("lang") if html_tag else None

    return {
        "_input": url,
        "_source": "S1-jsonld+html",
        "_scrapedAt": utc_now_iso(),
        "headline": headline,
        "description": _meta_content(soup, **{"name": "description"}) or _clean_text(ld.get("description")),
        "articleBody": article_body,
        "author": _ld_authors(ld) or _meta_content(soup, **{"name": "author"}),
        "datePublished": ld.get("datePublished") or _meta_content(soup, property="article:published_time"),
        "dateModified": ld.get("dateModified") or _meta_content(soup, property="article:modified_time"),
        "section": _meta_content(soup, property="article:section") or _section_from_url(url),
        "image": _meta_content(soup, property="og:image") or _ld_image(ld),
        "keywords": _meta_content(soup, **{"name": "keywords"}),
        "_lang": lang,
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_rss_items(xml_text: str) -> list[dict]:
    soup = BeautifulSoup(xml_text, "xml")
    items = []
    for item in soup.find_all("item"):
        title = item.find("title")
        link = item.find("link")
        teaser = item.find("description")
        category = item.find("category")
        pub_date = item.find("pubDate")
        guid = item.find("guid")

        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": _clean_text(title.text) if title and title.text else None,
                "link": _clean_text(link.text) if link and link.text else None,
                "teaser": _clean_text(teaser.text) if teaser and teaser.text else None,
                "category": _clean_text(category.text) if category and category.text else None,
                "pubDate": _clean_text(pub_date.text) if pub_date and pub_date.text else None,
                "guid": _clean_text(guid.text) if guid and guid.text else None,
            }
        )
    return items
