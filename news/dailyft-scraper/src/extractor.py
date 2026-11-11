"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html   -- ft.lk has NO ld+json anywhere on article pages (confirmed
               absent across all sampled templates). All fields are pulled
               from plain HTML/meta tags instead:
                 headline    <- h1.innerheader
                 deck        <- header.inner-content > ul > li (a one-line
                                subheading -- present on hard-news articles,
                                absent on opinion/column pieces; optional)
                 description <- meta[property=og:description]
                 datePublished/dateModified <- meta[itemprop=datePublished
                                / dateModified] (the only itemprop
                                microdata this CMS emits -- no headline/
                                author microdata)
               Full body text comes from header.inner-content: any
               <table> elements inside it are decomposed first (these are
               pull-image + caption widgets, not body content -- confirmed
               on a hard-news sample), then every remaining <p> tag
               (recursive, since paragraphs can be nested inside styled
               wrapper spans) has its inner HTML split on runs of <br>
               tags into paragraph fragments -- this project's CMS mixes
               real <p>-per-paragraph markup (opinion/column template)
               with a single giant <p> whose paragraphs are separated by
               <br><br> instead (hard-news template), and this approach
               handles both without needing template-specific branches.
  Soft-404  -- a nonexistent article URL returns HTTP 200 with NO
               header.inner-content / h1.innerheader at all, and
               <title> exactly matches the homepage's own title
               ("Sri Lanka's only national business newspaper | Daily
               FT") -- confirmed on a synthetic out-of-range article ID.
               Both conditions together (title match AND h1 missing) are
               required before treating it as SoftNotFound, so that a
               genuine future template change (h1 missing for some other
               reason, on a page that isn't the homepage-fallback) still
               raises UnexpectedShape instead of being silently
               misclassified as "not found".
  S2-rss    -- `/rss/top-story/26`, one of several per-section RSS 2.0
               feeds discovered via `/rss` (an HTML index page linking
               feeds for each section, not itself a feed) -- confirmed
               fresh (newest item was newer than the article sampled
               minutes earlier during recon) and spans multiple sections,
               not just a single narrow category. `pubDate` uses a
               non-standard format ("Monday, 24 August 2026 06:28", not
               RFC 822) -- passed through as the raw site string rather
               than reformatted, per raw-passthrough convention.

No author byline field was found anywhere in metadata or near the
byline/date area on any sampled article (the `dc:creator` in the RSS feed
is a Cloudflare email-obfuscation placeholder, not a journalist name) --
`author` is intentionally omitted from the output rather than fabricated.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.constants import HOME_TITLE

_BR_RUN_RE = re.compile(r"(?:<br\s*/?>\s*)+", re.IGNORECASE)


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


class SoftNotFound(Exception):
    """Page returned HTTP 200 but is actually the soft-404 homepage shell."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _meta_content(soup: BeautifulSoup, **attrs) -> str | None:
    tag = soup.find("meta", attrs=attrs)
    return tag.get("content") if tag else None


def _extract_body(container) -> str:
    for table in container.find_all("table"):
        table.decompose()
    paragraphs: list[str] = []
    for p in container.find_all("p"):
        inner = p.decode_contents()
        for fragment in _BR_RUN_RE.split(inner):
            frag_soup = BeautifulSoup(fragment, "lxml")
            text = frag_soup.get_text(" ", strip=True).replace("\xa0", " ").strip()
            if text:
                paragraphs.append(text)
    return "\n\n".join(paragraphs)


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    h1 = soup.select_one("h1.innerheader")
    container = soup.select_one("header.inner-content")
    title_tag = soup.find("title")
    page_title = title_tag.get_text(strip=True) if title_tag else None

    if h1 is None and container is None and page_title == HOME_TITLE:
        raise SoftNotFound("Page is the homepage shell -- article does not exist.")

    if h1 is None:
        raise UnexpectedShape("No h1.innerheader found -- page shape has likely changed.")
    if container is None:
        raise UnexpectedShape("No header.inner-content found -- page shape has likely changed.")

    article_body = _extract_body(container)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    deck_el = container.select_one("ul > li")
    deck = deck_el.get_text(" ", strip=True) if deck_el else None

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "headline": h1.get_text(strip=True),
        "deck": deck,
        "description": _meta_content(soup, property="og:description"),
        "articleBody": article_body,
        "datePublished": _meta_content(soup, itemprop="datePublished"),
        "dateModified": _meta_content(soup, itemprop="dateModified"),
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
        guid = item.find("guid")
        description = item.find("description")
        pub_date = item.find("pubDate")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "description": description.text.strip() if description and description.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
            }
        )
    return items
