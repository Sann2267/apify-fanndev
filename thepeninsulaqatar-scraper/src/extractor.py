"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html     -- thepeninsulaqatar.com's article pages carry exactly one
                 `<script type="application/ld+json">` block, and it is a
                 site-wide `WebPage` navigation schema (category menu
                 `hasPart` list) -- there is no `NewsArticle`/`Article`
                 ld+json block at all. Every field below instead comes
                 from <meta> tags (the template emits the same values
                 four times over, as `itemprop=*`, `article:*`, `DC.*`,
                 and `og:*`/`twitter:*` -- `itemprop` is used as primary,
                 the others as fallback) and two stable HTML anchors:
                   - `h3.title-tag` -- breadcrumb, exactly two <a> tags:
                     the main category (e.g. "Qatar", "World") and a
                     subcategory (e.g. "General", "Americas", "Europe").
                   - `h5.title` (inside `div.in-title`) -- a wire/byline
                     source tag: "QNA" (Qatar News Agency), "AFP", or
                     "The Peninsula" for staff-written pieces. This is
                     the actual per-article byline; the `article:author`
                     / `itemprop=author` meta tags always carry the
                     generic org name "The Peninsula Newspaper" instead
                     (upstream quirk -- kept here as `publisher`, not
                     `author`, to reflect what it actually is).
                 Full text lives in `div.con-text`: the template emits
                 *two* per page -- the first is always empty (a leftover
                 share-widget wrapper), the second holds the real
                 paragraphs. Paragraphs are malformed in raw HTML (each
                 wrapped in one stray outer `<p>` around all the real
                 `<p>` tags), but BeautifulSoup's `lxml` parser
                 auto-closes the stray outer tag, so *direct-child*
                 `<p>` collection already yields clean text with no
                 extra unwrapping needed.
  S2-sitemap  -- `/sitemap.xml` is a `<sitemapindex>` of monthly shards
                 (`/sitemap_articles-<year>-<month>.xml`, month has no
                 leading zero), each a Google News sitemap
                 (`news:title`/`news:publication_date`/`lastmod`/`loc`),
                 newest article first. No RSS feed exists (`/feed`,
                 `/rss`, `/rss.xml` all soft-200 to the generic listing
                 template -- see CRAWLING_METHOD.md), so the sitemap is
                 the only available `latest`-mode source.
"""

from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/XML shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _meta(soup: BeautifulSoup, name: str | None = None, prop: str | None = None) -> str | None:
    if name:
        tag = soup.find("meta", attrs={"name": name})
    else:
        tag = soup.find("meta", attrs={"property": prop})
    content = tag.get("content") if tag else None
    return content.strip() if isinstance(content, str) and content.strip() else None


def _extract_body(soup: BeautifulSoup) -> str:
    divs = soup.select("div.con-text")
    if not divs:
        raise UnexpectedShape("No div.con-text element found -- page shape has likely changed.")
    paragraphs = []
    for div in divs:
        for el in div.find_all(["p", "h2", "h3", "blockquote"], recursive=False):
            text = el.get_text(" ", strip=True)
            if text:
                paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _extract_breadcrumb(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    tag = soup.select_one("h3.title-tag")
    if not tag:
        return None, None
    links = tag.find_all("a")
    category = links[0].get_text(strip=True) if len(links) > 0 else None
    subcategory = links[1].get_text(strip=True) if len(links) > 1 else None
    return category or None, subcategory or None


def _extract_headline(soup: BeautifulSoup) -> str | None:
    h1 = soup.select_one("div.tag-art > h1.title")
    if h1:
        text = h1.get_text(strip=True)
        if text:
            return text
    return _meta(soup, name="news_title") or _meta(soup, prop="og:title")


def _extract_source_tag(soup: BeautifulSoup) -> str | None:
    tag = soup.select_one("div.in-title h5.title")
    return tag.get_text(strip=True) if tag else None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    headline = _extract_headline(soup)
    if not headline:
        raise UnexpectedShape("No headline found in <h1> or meta tags -- page shape has likely changed.")

    article_body = _extract_body(soup)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    category, subcategory = _extract_breadcrumb(soup)

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "headline": headline,
        "description": _meta(soup, name="description"),
        "articleBody": article_body,
        "author": _extract_source_tag(soup),
        "publisher": _meta(soup, prop="article:author") or _meta(soup, name="author"),
        "category": category,
        "subcategory": subcategory,
        "datePublished": _meta(soup, name="datePublished") or _meta(soup, prop="article:published_time"),
        "dateModified": _meta(soup, name="dateModified") or _meta(soup, prop="article:modified_time"),
        "image": _meta(soup, prop="og:image") or _meta(soup, name="image"),
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
        raise UnexpectedShape("No <url> elements found in article sitemap -- sitemap shape has likely changed.")
    results = []
    for u in urls:
        loc = u.find("loc")
        title = u.find("news:title")
        pub_date = u.find("news:publication_date")
        lastmod = u.find("lastmod")
        results.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": loc.text.strip() if loc and loc.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "lastmod": lastmod.text.strip() if lastmod and lastmod.text else None,
            }
        )
    return results
