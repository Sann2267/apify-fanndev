"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see constants.py / CRAWLING_METHOD.md for full recon
notes):
  S1-html   -- fijitimes.com.fj (WordPress + Yoast SEO) emits **zero**
               ld+json of any kind on article pages (confirmed on 3
               samples) -- unusual for a Yoast install, but real. Every
               field comes from plain HTML: the headline from
               `h1.fijitimes_title`, the full body from
               `div.entry-content.post_content > p` paragraphs, and the
               rest from `<meta>` tags. The page emits its OpenGraph/
               Twitter/article meta tags TWICE (a Yoast-labeled block
               followed by an unlabeled duplicate using the canonical
               `.com.fj` domain) -- `soup.find` naturally takes the FIRST
               occurrence of each field, which is the Yoast-labeled
               block; both blocks' `article:published_time` represent the
               same instant in different timezone notations so this is
               not a real conflict. Categories come from
               `a[rel="category tag"]` links (e.g. "Local News", "News",
               "Today's Main Story").
  S2-sitemap -- `/feed/` 301-redirects to the homepage (dead, matching
               this portfolio's prior experience with other small
               Commonwealth regional dailies), so `latest` mode reads
               `sitemap_index.xml`, picks the `post-sitemap*.xml` entry
               with the newest `<lastmod>`, and takes that file's last N
               `<url>` entries (confirmed ascending-chronological file
               order -- oldest first, newest last). This generic Yoast
               sitemap (not a Yoast *News* SEO sitemap) carries only
               `loc`/`lastmod`/`image:loc` per entry, no title or true
               publish timestamp -- `lastmod` is the closest available
               proxy and is labeled as such, not as `pubDate`.
"""

import html
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.constants import BASE_URL


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _meta_content(soup: BeautifulSoup, **attrs) -> str | None:
    tag = soup.find("meta", attrs=attrs)
    content = tag.get("content") if tag else None
    return html.unescape(content) if content else None


def _extract_body(soup: BeautifulSoup) -> str:
    container = soup.select_one("div.entry-content.post_content")
    if container is None:
        raise UnexpectedShape("No div.entry-content.post_content element found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    return "\n\n".join(paragraphs)


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    h1 = soup.select_one("h1.fijitimes_title")
    headline = h1.get_text(strip=True) if h1 else None
    if not headline:
        raise UnexpectedShape("No h1.fijitimes_title element found -- page shape has likely changed.")

    article_body = _extract_body(soup)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    categories = [
        html.unescape(a.get_text(strip=True))
        for a in soup.select('a[rel="category tag"]')
        if a.get_text(strip=True)
    ]

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "headline": headline,
        "articleBody": article_body,
        "author": _meta_content(soup, name="author"),
        "description": _meta_content(soup, name="description"),
        "categories": categories or None,
        "datePublished": _meta_content(soup, property="article:published_time"),
        "dateModified": _meta_content(soup, property="article:modified_time"),
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


def extract_sitemap_index(xml_bytes: bytes) -> str:
    """Return the URL of the newest `post-sitemap*.xml` page inside
    `sitemap_index.xml`.

    NOT sorted by each entry's own `<lastmod>` -- the unnumbered
    `post-sitemap.xml` (page 1) was observed with a spurious first `<url>`
    entry for the bare homepage (`https://www.fijitimes.com.fj/`) whose
    own `<lastmod>` ties with the true-newest page's, which would make a
    naive lastmod-sort pick the wrong (oldest-articles) page on a tie.
    Yoast lists post-type sitemap pages in ascending page order in the
    index (`post-sitemap.xml`, `post-sitemap2.xml`, `post-sitemap3.xml`,
    ...) -- confirmed by cross-checking every page's own first/last
    `<lastmod>` forms one continuous ascending timeline across pages, so
    the LAST matching entry in document order is reliably the newest
    page.
    """
    soup = BeautifulSoup(xml_bytes, "xml")
    sitemap_nodes = soup.find_all("sitemap")
    if not sitemap_nodes:
        raise UnexpectedShape("No <sitemap> elements found in sitemap_index.xml -- sitemap shape has likely changed.")

    post_sitemap_urls = [
        node.find("loc").text.strip()
        for node in sitemap_nodes
        if node.find("loc") and node.find("loc").text and "post-sitemap" in node.find("loc").text
    ]

    if not post_sitemap_urls:
        raise UnexpectedShape("No post-sitemap*.xml entries found in sitemap_index.xml -- sitemap shape has likely changed.")

    return post_sitemap_urls[-1]


def extract_sitemap_items(xml_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    url_nodes = soup.find_all("url")
    if not url_nodes:
        raise UnexpectedShape("No <url> elements found in post sitemap -- sitemap shape has likely changed.")

    results = []
    for url_node in url_nodes:
        loc = url_node.find("loc")
        link = loc.text.strip() if loc and loc.text else None
        if not link:
            continue
        # post-sitemap.xml (page 1) was observed with a spurious entry for
        # the bare homepage itself -- not an article. Skip it defensively
        # on every page.
        if link.rstrip("/") in (BASE_URL, ""):
            continue
        lastmod_tag = url_node.find("lastmod")
        image_tag = url_node.find("image:loc")
        results.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "link": link,
                "lastmod": lastmod_tag.text.strip() if lastmod_tag and lastmod_tag.text else None,
                "image": image_tag.text.strip() if image_tag and image_tag.text else None,
            }
        )

    # Confirmed ascending-chronological (oldest first) in file order --
    # reverse so newest is first, matching this portfolio's latest-mode
    # convention. `limit` slicing happens in main.py after this reversal.
    results.reverse()
    return results
