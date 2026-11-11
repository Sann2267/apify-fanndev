"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html         -- chinadaily.com.cn emits a `NewsArticle` ld+json block
                     (a single `<script type="application/ld+json">` tag,
                     confirmed on all 4 sampled articles -- unlike TASS
                     there is no `Organization`/`SiteNavigationElement`
                     clutter to scan past, but the extractor still scans
                     all ld+json blocks and picks the one whose `@type` is
                     `NewsArticle` for robustness against a future template
                     that adds more blocks). It carries `headline`, `image`,
                     `datePublished`, `dateModified`, `publisher`
                     (`Organization`, name inconsistently either
                     `"China Daily"` or `"chinadaily.com.cn"` depending on
                     which CMS template rendered the page -- passed through
                     raw, not normalized), and sometimes `author`
                     (`Person`) and `description` -- both are absent on
                     wire-service/video-type content with no named byline
                     (confirmed on one sample). **No `articleBody`** in
                     ld+json, same limitation as TASS.
                     Full text comes from HTML `#Content` -- this element
                     ID is stable across at least 3 different CMS template
                     generations seen in sampling (old `class="info"` byline
                     template, newer `class="Artical_Content"` template, and
                     a video-article template), while the *class* on that
                     div is not stable, so extraction selects by `id`, not
                     class. Paragraphs are plain unwrapped `<p>` tags (like
                     TASS, NOT the `<br>`-separated Global-Times style) --
                     the lead image's `<figcaption>` sits as a sibling of
                     the `<p>` tags, not inside one, so it is naturally
                     excluded by selecting only `<p>` tags (no explicit
                     decompose step needed, unlike Global Times' duplicate
                     picture caption).
  S2-html-listing -- `/rss/china_rss.xml` (HTTP 200, newest item Dec 2017)
                     and `/sitemap.xml` (HTTP 200, newest `lastmod` 2014)
                     are both dead/frozen artifacts, unusable for "latest"
                     mode. Instead the homepage is scraped for `<a href>`
                     links matching the article URL pattern
                     `/a/YYYYMM/DD/WS<hex>.html`. Because that ID is
                     zero-padded and chronological, sorting the URLs
                     lexically descending reproduces newest-first order
                     without needing to visit each article page. Each link
                     appears twice in the markup (once wrapping a thumbnail
                     `<img>` with no text, once wrapping the headline text)
                     -- the extractor keeps the longest non-empty anchor
                     text seen for a given URL as the title.

Known CMS quirk NOT handled by this extractor (see CRAWLING_METHOD.md):
some "photo essay" articles paginate their body across multiple pages
(`..._2.html`, `..._3.html`, ...) -- only page 1's paragraphs are
captured. A handful of `/subsites/...`-style sponsored microsite pages use
a completely different template with no ld+json and no `#Content` div at
all; these correctly raise `UnexpectedShape` (fail loud) rather than being
silently guessed at.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

ARTICLE_URL_RE = re.compile(r"/a/(20\d{2})(\d{2})/(\d{2})/(WS[0-9a-f]+)\.html")


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


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    body_el = soup.find(id="Content")
    if body_el is None:
        raise UnexpectedShape("No #Content element found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in body_el.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    article_body = "\n\n".join(paragraphs)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    news_article = _find_news_article(soup)
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    author = news_article.get("author")
    publisher = news_article.get("publisher") or {}

    return {
        "_input": url,
        "_source": "S1-html",
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


def _normalize_url(href: str) -> str:
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return "https://www.chinadaily.com.cn" + href
    return href


def extract_latest_items(html_text: str) -> list[dict]:
    soup = BeautifulSoup(html_text, "lxml")

    titles: dict[str, str] = {}
    order: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not ARTICLE_URL_RE.search(href):
            continue
        norm = _normalize_url(href)
        text = a.get_text(strip=True)
        if norm not in titles:
            order.append(norm)
            titles[norm] = ""
        if text and len(text) > len(titles[norm]):
            titles[norm] = text

    def sort_key(link: str):
        m = ARTICLE_URL_RE.search(link)
        return m.groups() if m else ("", "", "", "")

    order.sort(key=sort_key, reverse=True)

    items = []
    for link in order:
        m = ARTICLE_URL_RE.search(link)
        year, month, day, _art_id = m.groups()
        items.append(
            {
                "_input": "latest",
                "_source": "S2-html-listing",
                "_scrapedAt": utc_now_iso(),
                "title": titles[link] or None,
                "link": link,
                # Day precision only -- derived from the URL path, not a
                # true publish timestamp. Fetch the article (article mode)
                # for the exact `datePublished` from its ld+json block.
                "urlDate": f"{year}-{month}-{day}",
            }
        )
    return items
