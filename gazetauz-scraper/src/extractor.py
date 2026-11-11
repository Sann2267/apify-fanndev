"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-microdata+html -- gazeta.uz's `/en/` article pages carry **NO
             `<script type="application/ld+json">` block at all**
             (confirmed absent on every sampled article). Instead all
             structured metadata is embedded directly in the visible HTML
             as schema.org **microdata** (`itemscope`/`itemprop`
             attributes on ordinary tags), not a separate JSON blob:
               headline         <- h1#article_title[itemprop~="headline"]
               alternativeHeadline (dek) <- h4[itemprop=alternativeHeadline]
               datePublished    <- meta[itemprop=datePublished] (full ISO
                                   8601 with +05:00 offset, e.g.
                                   "2026-08-26T09:24:44+05:00")
               author           <- span[itemprop=author] -- always an
                                   institutional byline ("Gazeta" or
                                   "Gazeta.uz"), never a personal name, even
                                   on guest op-eds (confirmed on a David
                                   Cameron-bylined op-ed: itemprop=author
                                   still reads "Gazeta.uz", not "David
                                   Cameron" -- kept as raw passthrough, not
                                   corrected)
               section          <- first span[itemprop=name] inside the
                                   itemtype=BreadcrumbList block
               tags             <- all span[itemprop=about] text values
               articleBody      <- div#redactor[itemprop=articleBody]
               image            <- meta[property=og:image] (cleaner than
                                   the body's own itemprop=image tags,
                                   which also mark inline/chart images, not
                                   just the lead image)
             Confirmed consistent across 6 sampled articles spanning the
             "news" (type-news) and "column"/op-ed (type-articles)
             templates.

  Malformed-HTML ad markup -- the article body's raw HTML embeds an inline
             ad widget (`div.inpage-ad`, plus a `<script>` block) **nested
             inside a `<p>` tag** alongside an image-caption `<span>` (an
             invalid `<div>`/`<script>` inside `<p>`, which lxml's HTML
             parser tolerates without repositioning). `_extract_body()`
             `.decompose()`s every `div.inpage-ad` and `<script>` tag
             found inside the body container BEFORE walking `<p>` tags, so
             no ad copy or JS leaks into `articleBody`. The image caption
             text that shares the same `<p>` (from a
             `span.fr-img-caption`) is NOT filtered out -- it reads as a
             normal sentence in-line with the surrounding paragraphs on
             the live page too, so it is kept, matching raw-passthrough
             philosophy.

  Unsupported template -- a small subset of long-form pieces under
             `/en/list/reporting/` ("Stories") use a completely different,
             Tilda-page-builder-based multimeadia template (no
             `div#redactor`, no `h1#article_title`, no
             `itemprop=articleBody` anywhere -- confirmed on a sampled
             census-reporting story) with drag-and-drop `t-rec`/`t004`/
             `t107`-style blocks instead of the standard article markup.
             Not supported by this extractor -- `extract_article()` raises
             `UnexpectedShape` for these pages (fail loud), a documented
             known limit (see CRAWLING_METHOD.md), rather than silently
             returning an empty/partial record.

  S2-rss   -- `/en/rss/`, a standard RSS 2.0 feed (English edition only),
             newest-first, 20 items. Teaser-only: `<description>` carries
             a short lede (NOT the full article body, unlike
             `kazinform-scraper`'s `feed.xml`), plus `<enclosure>` for the
             lead image and `<dc:creator>` (always "Gazeta", same
             institutional-byline pattern as the article page). The
             `<description>` CDATA embeds literal HTML entities
             (`&nbsp;`, `&mdash;`, `&rsquo;`) as plain text -- CDATA is not
             entity-decoded by XML spec, so an XML parser hands them back
             unresolved. `_clean_text()` runs `html.unescape()` on every
             cleaned field (both modes) to resolve these into their real
             characters rather than leaking raw entity codes into the
             dataset.
"""

import html
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_text(text: str | None) -> str | None:
    if not text:
        return None
    text = html.unescape(text.replace("\xa0", " "))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _meta_content(soup: BeautifulSoup, **attrs) -> str | None:
    tag = soup.find("meta", attrs=attrs)
    return tag.get("content") if tag else None


def _extract_body(container) -> str:
    """Strip inline ad widgets/scripts, then join <p> text.

    See module docstring -- `div.inpage-ad` + its <script> sibling are
    embedded inside a body <p> tag; both are decomposed before walking
    paragraphs so no ad copy/JS leaks into articleBody.
    """
    for tag in container.find_all("script"):
        tag.decompose()
    for tag in container.select("div.inpage-ad"):
        tag.decompose()
    for tag in container.select("#extra"):
        tag.decompose()
    paragraphs = [_clean_text(p.get_text(" ", strip=True)) for p in container.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    return "\n\n".join(paragraphs)


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    h1 = soup.select_one("h1#article_title")
    container = soup.select_one("div#redactor[itemprop=articleBody]")
    if h1 is None or container is None:
        raise UnexpectedShape(
            "No h1#article_title / div#redactor[itemprop=articleBody] found -- "
            "either the page shape changed, or this is an unsupported longform "
            "'Stories' template (see CRAWLING_METHOD.md known limits)."
        )

    article_body = _extract_body(container)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    dek_el = soup.select_one("h4[itemprop=alternativeHeadline]")
    author_el = soup.select_one("span[itemprop=author]")
    section_el = soup.select_one('span[itemtype="https://schema.org/BreadcrumbList"] span[itemprop=name]')
    tags = [
        _clean_text(t.get_text(" ", strip=True))
        for t in soup.select("div.articleTags span[itemprop=about]")
    ]
    tags = [t for t in tags if t]

    return {
        "_input": url,
        "_source": "S1-microdata+html",
        "_scrapedAt": utc_now_iso(),
        "headline": _clean_text(h1.get_text(" ", strip=True)),
        "dek": _clean_text(dek_el.get_text(" ", strip=True)) if dek_el else None,
        "description": _meta_content(soup, property="og:description"),
        "articleBody": article_body,
        "author": _clean_text(author_el.get_text(" ", strip=True)) if author_el else None,
        "section": _clean_text(section_el.get_text(" ", strip=True)) if section_el else None,
        "tags": tags,
        "datePublished": _meta_content(soup, itemprop="datePublished"),
        "image": _meta_content(soup, property="og:image"),
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
        description = item.find("description")
        pub_date = item.find("pubDate")
        enclosure = item.find("enclosure")
        creator = item.find("dc:creator") or item.find("creator")

        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "description": _clean_text(description.text) if description and description.text else None,
                "author": creator.text.strip() if creator and creator.text else None,
                "image": enclosure.get("url") if enclosure else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
            }
        )
    return items
