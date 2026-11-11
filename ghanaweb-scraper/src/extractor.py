"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html    -- ghanaweb.com emits ONE ld+json `@graph` array per article
               page holding a `NewsArticle` node and a `BreadcrumbList`
               node. The `NewsArticle` node carries `headline`,
               `description`, `datePublished`/`dateModified`,
               `articleSection` (category), `thumbnailUrl`, `image`
               (object: url/caption/width/height) and `author` -- but
               **no `articleBody`**. For staff-written News/Sports/
               Business/Entertainment pieces `author` is a
               `NewsMediaOrganization` object (`"GhanaWeb"`, with a
               `noBylinesPolicy` link -- individual reporters are
               deliberately not credited in ld+json); for Opinions/
               Features pieces `author` is simply `null`.
               Full text comes from HTML: `div.article-content-area`.
               This legacy CMS does not wrap paragraphs in `<p>` tags --
               the whole body is one `<p>` with `<br>` tags separating
               lines (same shape as globaltimes-scraper's Global Times
               template). In-body keyword mentions (e.g. "Parliament")
               are auto-linked to `people/person.php` profile pages --
               sometimes with several *empty* duplicate `<a>` tags
               immediately before the one carrying the visible text --
               but a plain `get_text()` walk reconstructs the sentence
               correctly regardless, since BeautifulSoup concatenates
               text nodes in document order with no inserted separator.
               **Key quirk (byline signature):** News/Sports/Business/
               Entertainment articles end the real body with a standalone
               2-part reporter/editor-initials signature line (e.g.
               `"MRA/MA"`, `"DR/MA"`, `"JHM/EB"`) immediately followed by
               an unrelated "watch this other story" bold-linked
               headline + a YouTube/Twitter embed -- all of which is
               promo noise, not part of the article. The extractor
               detects the first paragraph matching `^[A-Z]{1,5}/[A-Z]{1,5}$`
               and truncates the body there, keeping the signature in a
               separate `reporterInitials` field. Opinions/Features
               pieces (verified on a sampled columnist piece) have no
               such signature and no trailing promo -- the full
               paragraph list is kept as-is when no signature line is
               found.
               A separate `<p class="floatRight">` element (outside the
               ld+json, sibling of the body) carries a `<strong>Label:
               </strong><a>Name</a>` byline block -- `"Source: www.
               ghanaweb.com"` on staff pieces, `"Columnist: <Name>"` on
               opinion pieces -- captured as `bylineLabel`/`bylineName`
               since it's the only place an individual columnist's name
               appears (ld+json `author` is `null` for those).
  S2-sitemap -- Google News sitemap (`/sitemaps/news.xml`, advertised in
               robots.txt). Observed updating in near-real-time (items
               published under a minute before fetch). Fields:
               `news:title`, `loc` (article URL), `news:publication_date`
               (proper ISO-8601 with timezone), `news:language`. No
               `news:keywords` element on this feed (unlike Global
               Times). `section` is derived from the URL path segment
               right after `/GhanaHomePage/` (e.g. `NewsArchive`,
               `SportsArchive`, `business`, `entertainment`) since the
               feed carries no explicit category field of its own.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

SIGNATURE_RE = re.compile(r"^[A-Z]{1,5}/[A-Z]{1,5}$")
ARTICLE_ID_RE = re.compile(r"-(\d+)$")


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_article_id(url: str) -> str | None:
    m = ARTICLE_ID_RE.search(url.split("?")[0].rstrip("/"))
    return m.group(1) if m else None


def _find_graph_node(soup: BeautifulSoup, type_name: str) -> dict | None:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        graph = data.get("@graph")
        nodes = graph if isinstance(graph, list) else [data]
        for node in nodes:
            if isinstance(node, dict) and node.get("@type") == type_name:
                return node
    return None


def _extract_byline(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    label_el = soup.select_one("p.floatRight")
    if label_el is None:
        return None, None
    strong = label_el.find("strong")
    link = label_el.find("a")
    if strong is None:
        return None, None
    label = strong.get_text(strip=True).rstrip(":")
    name = link.get_text(strip=True) if link else label_el.get_text(strip=True)
    return label or None, name or None


def _extract_body(soup: BeautifulSoup) -> tuple[str, str | None]:
    container = soup.select_one("div.article-content-area")
    if container is None:
        raise UnexpectedShape("No div.article-content-area element found -- page shape has likely changed.")

    for br in container.find_all("br"):
        br.replace_with("\n")

    lines = [line.strip() for line in container.get_text().split("\n")]
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if line:
            current.append(line)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))

    reporter_initials = None
    for i, para in enumerate(paragraphs):
        if SIGNATURE_RE.match(para):
            reporter_initials = para
            paragraphs = paragraphs[:i]
            break

    return "\n\n".join(paragraphs), reporter_initials


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article_body, reporter_initials = _extract_body(soup)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    news_article = _find_graph_node(soup, "NewsArticle")
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json node found -- page shape has likely changed.")

    author = news_article.get("author") or {}
    author_name = author.get("name") if isinstance(author, dict) else author

    byline_label, byline_name = _extract_byline(soup)

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "articleId": _extract_article_id(url),
        "headline": news_article.get("headline"),
        "description": news_article.get("description"),
        "articleBody": article_body,
        "reporterInitials": reporter_initials,
        "author": author_name,
        "bylineLabel": byline_label,
        "bylineName": byline_name,
        "category": news_article.get("articleSection"),
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "thumbnailUrl": news_article.get("thumbnailUrl"),
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


def extract_sitemap_items(xml_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    url_nodes = soup.find_all("url")
    if not url_nodes:
        raise UnexpectedShape("No <url> elements found in news sitemap -- feed shape has likely changed.")
    results = []
    for url_node in url_nodes:
        loc = url_node.find("loc")
        title = url_node.find("news:title")
        pub_date = url_node.find("news:publication_date")
        language = url_node.find("news:language")
        link = loc.text.strip() if loc and loc.text else None
        section = None
        if link and "/GhanaHomePage/" in link:
            after = link.split("/GhanaHomePage/", 1)[1]
            section = after.split("/", 1)[0] or None
        results.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "articleId": _extract_article_id(link) if link else None,
                "title": title.text.strip() if title and title.text else None,
                "link": link,
                "section": section,
                "publicationDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "language": language.text.strip() if language and language.text else None,
            }
        )
    return results
