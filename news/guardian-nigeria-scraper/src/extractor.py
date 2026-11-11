"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- guardian.ng (The Guardian Nigeria, WordPress + Yoast SEO --
             NOT related to the UK's The Guardian) emits ONE
             `<script type="application/ld+json">` block per article page, a
             Yoast-style `@graph` array of cross-referenced nodes
             (`NewsArticle`, `WebPage`, `ImageObject`, `BreadcrumbList`,
             `WebSite`, `Organization`, `Person`). Unlike Punch (no
             `Organization` node at all) and Premium Times (`author` as a
             bare `{"@id": ...}` ref), this site's `NewsArticle.author` is a
             LIST of fully inline `Person` objects (name, a full bio
             paragraph in `description`, `url`, `image`, `sameAs`), and
             `publisher` IS a bare `{"@id": "...#organization"}` reference
             that resolves to a real `Organization` node
             (`name: "Guardian Nigeria"`) -- so publisher comes from the
             graph itself, not a `<meta property="og:site_name">` fallback.
             The `NewsArticle` node carries `headline`, `datePublished`,
             `dateModified`, `wordCount`, `keywords`, `articleSection`,
             `thumbnailUrl` -- but **no `articleBody`**. No double-HTML-
             escaping quirk observed in this graph's text values (unlike
             Punch's `"Business &amp; Economy"`) on any of the 4 samples
             checked -- `html.unescape()` is still applied to every text
             value pulled from the graph for robustness against a future
             shape change, it's a no-op when there's nothing to unescape.
             Full body text comes from HTML: `div.post-content`, direct-
             child `<p>` tags only (`recursive=False`) -- confirmed this
             exact class string appears exactly ONCE per article page (ad
             slots inside the container are `<div>` elements, not `<p>`, so
             they're skipped automatically by the tag-name filter without
             needing extra scoping).
             A page that 200-OKs but is not an article at all (e.g.
             `/privacy-policy/`) emits a `WebPage`/`BreadcrumbList`/
             `WebSite`/`Organization` graph with no `NewsArticle` node --
             detected explicitly and reported as `_error: "not_article"`
             rather than a schema-drift crash.
             A genuinely deleted/never-existed slug returns a REAL HTTP 404
             (confirmed on a deliberately-invented slug) -- no soft-404
             quirk observed.
  S2-sitemap -- `/news-sitemap.xml` (Yoast News SEO sitemap, referenced from
             robots.txt). `/feed` (and `/feed/`, `/latest-news/`) are
             blocked by Cloudflare with a hard 403 across every TLS profile
             tried -- a path-specific WAF rule, not a general fingerprint
             block (the homepage, article pages, and this sitemap all 200
             cleanly on the same profile). Each `<url>` carries `loc`,
             `news:news/news:publication_date` (ISO 8601, real per-article
             timestamp), and `news:news/news:title` -- confirmed already
             newest-first in file order (295 entries observed), but sorted
             descending by publication_date defensively anyway in case that
             ordering isn't guaranteed on every fetch.
"""

import html
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


class ArticleNotFound(Exception):
    """The page 200-OK'd but is not an article (no NewsArticle node in the
    schema graph) -- e.g. a static page like /privacy-policy/. An expected
    per-input failure, not a schema-drift crash. See CRAWLING_METHOD.md.
    """


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _unescape(value):
    if isinstance(value, str):
        return html.unescape(value)
    if isinstance(value, list):
        return [_unescape(v) for v in value]
    return value


def _find_schema_graph(soup: BeautifulSoup) -> list | None:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and isinstance(data.get("@graph"), list):
            return data["@graph"]
    return None


def _index_graph(graph: list) -> dict:
    return {node["@id"]: node for node in graph if isinstance(node, dict) and node.get("@id")}


def _resolve_refs(value, index: dict) -> list[dict]:
    """`value` may be a single node, a single {"@id": ...} ref, or a list of
    either. Returns the resolved node dicts (unresolvable refs dropped).
    """
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    resolved = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if set(item.keys()) == {"@id"}:
            node = index.get(item["@id"])
            if node:
                resolved.append(node)
        else:
            resolved.append(item)
    return resolved


def _find_node(graph: list, type_names: set[str]) -> dict | None:
    for node in graph:
        if not isinstance(node, dict):
            continue
        node_type = node.get("@type")
        types = node_type if isinstance(node_type, list) else [node_type]
        if any(t in type_names for t in types):
            return node
    return None


def _extract_body(soup: BeautifulSoup) -> str:
    container = soup.select_one("div.post-content")
    if container is None:
        raise UnexpectedShape("No div.post-content found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p", recursive=False) if p.get_text(strip=True)]
    return "\n\n".join(paragraphs)


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    graph = _find_schema_graph(soup)
    if graph is None:
        raise UnexpectedShape("No Yoast @graph ld+json block found -- page shape has likely changed.")

    article = _find_node(graph, {"NewsArticle", "Article"})
    if article is None:
        # Non-article pages (e.g. /privacy-policy/) 200-OK with a
        # WebPage/BreadcrumbList/WebSite/Organization graph and no
        # NewsArticle node.
        raise ArticleNotFound(f"No NewsArticle node in schema graph for {url} -- not an article page.")

    index = _index_graph(graph)

    author_nodes = _resolve_refs(article.get("author"), index)
    author_names = [html.unescape(n["name"]) for n in author_nodes if n.get("name")]

    publisher_nodes = _resolve_refs(article.get("publisher"), index)
    publisher = html.unescape(publisher_nodes[0]["name"]) if publisher_nodes and publisher_nodes[0].get("name") else None
    if publisher is None:
        og_site_name = soup.find("meta", attrs={"property": "og:site_name"})
        publisher = og_site_name.get("content") if og_site_name else None

    article_body = _extract_body(soup)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    description = meta_desc_tag.get("content") if meta_desc_tag else None
    if not description:
        webpage = _find_node(graph, {"WebPage"})
        description = webpage.get("description") if webpage else None

    return {
        "_input": url,
        "_source": "S1-jsonld+html",
        "_scrapedAt": utc_now_iso(),
        "headline": _unescape(article.get("headline")),
        "description": description,
        "articleBody": article_body,
        "author": ", ".join(author_names) if author_names else None,
        "publisher": publisher,
        "articleSection": _unescape(article.get("articleSection")),
        "keywords": _unescape(article.get("keywords")),
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "thumbnailUrl": article.get("thumbnailUrl"),
        "wordCount": article.get("wordCount"),
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
        raise UnexpectedShape("No <url> elements found in news sitemap -- sitemap shape has likely changed.")

    results = []
    for url_node in url_nodes:
        loc = url_node.find("loc")
        link = loc.text.strip() if loc and loc.text else None
        if not link:
            continue
        title_tag = url_node.find("news:title")
        pub_date_tag = url_node.find("news:publication_date")
        title = html.unescape(title_tag.text.strip()) if title_tag and title_tag.text else None
        pub_date = pub_date_tag.text.strip() if pub_date_tag and pub_date_tag.text else None
        results.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title,
                "link": link,
                "pubDate": pub_date,
            }
        )

    # Confirmed newest-first in file order on every sample taken, but sort
    # descending by publication date defensively anyway.
    results.sort(key=lambda r: r["pubDate"] or "", reverse=True)
    return results
