"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- theprint.in (WordPress + tagDiv "Newspaper" theme +
             Yoast SEO) emits ONE `<script type="application/ld+json">`
             block per article page, a Yoast-style `@graph` array of
             cross-referenced nodes (`Article`, `WebPage`, `ImageObject`,
             `BreadcrumbList`, `WebSite`, `Organization`, `Person`).
             `Article.author` is a list of `{"@id": ...}` refs that resolve
             against the graph to inline `Person` nodes (name + avatar +
             author archive URL); `Article.publisher` is a bare
             `{"@id": "...#organization"}` ref that resolves to the graph's
             own `Organization` node (`name: "ThePrint"`). The `Article`
             node carries `headline`, `datePublished`, `dateModified`,
             `wordCount`, `commentCount`, `keywords`, `articleSection`,
             `thumbnailUrl` -- but **no `articleBody`**. No double-HTML-
             escaping quirk observed in the graph's text values on any
             sample checked; `html.unescape()` is applied defensively to
             every text value pulled from the graph anyway.
             Full body text comes from HTML: `div.td-post-content` (the
             tagDiv Newspaper theme's article-body block). Unlike a simple
             single-level container, this theme nests the actual paragraphs
             two levels down inside an unclassed wrapper `<div>`
             (`div.tdb-block-inner > div` with no class), interleaved with
             sibling `div.code-block` ad-slot placeholders that carry no
             `<p>` tags at all -- so a full (recursive) `find_all("p")` on
             `div.td-post-content` picks up every real paragraph and no ad
             copy, with no extra scoping needed (confirmed: zero `<p>` tags
             carry any `class` attribute, i.e. no image-caption `<p>` tags
             leak into the body text either).
             A page that 200-OKs but is not an article at all would emit a
             graph with no `Article` node -- detected explicitly and
             reported as `_error: "not_article"` rather than a schema-drift
             crash (not directly observed on a real static page during
             recon, but the same defensive check used by every other
             Yoast-graph actor in this portfolio is kept here).
  S2-sitemap -- `/googlenews.xml` (Google News sitemap, referenced from
             robots.txt). The site-wide `/feed` RSS and `/wp-json/wp/v2/
             posts` REST API both return the SAME edge "Just a moment"
             challenge body as an uncached article page on every attempt,
             so the Google News sitemap is used instead -- it is never
             gated the same way (always returns full XML). Each `<url>`
             carries `loc`, `news:news/news:publication_date` (real
             per-article ISO 8601 timestamp), `news:news/news:title`,
             `news:news/news:keywords` (e.g. "reuters wire", "PTI wire" on
             wire-sourced pieces), and `image:loc`. Confirmed already
             newest-first in file order (1000 entries observed), but sorted
             descending by publication_date defensively anyway in case that
             ordering isn't guaranteed on every fetch.

Paywall: NONE observed. "premium"/"Premium" string hits on sampled article
pages all trace to the Yoast SEO Premium plugin comment and an unrelated
video-CTA widget class name (`tvc_go_premium`), not article-body gating. 4
articles sampled in depth (Judiciary, Feature/celebrity, Tech, Diplomacy)
all returned full, naturally-ending body text (closing editor credit line,
no "subscribe to continue reading" marker, articleBody length consistent
with the ld+json `wordCount` field) -- ThePrint is a free, open-access site.
"""

import html
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


class ArticleNotFound(Exception):
    """The page 200-OK'd but is not an article (no Article/NewsArticle node
    in the schema graph) -- e.g. a static page. An expected per-input
    failure, not a schema-drift crash. See CRAWLING_METHOD.md.
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
    container = soup.select_one("div.td-post-content")
    if container is None:
        raise UnexpectedShape("No div.td-post-content found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p") if p.get_text(strip=True)]
    return "\n\n".join(paragraphs)


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    graph = _find_schema_graph(soup)
    if graph is None:
        raise UnexpectedShape("No Yoast @graph ld+json block found -- page shape has likely changed.")

    article = _find_node(graph, {"NewsArticle", "Article"})
    if article is None:
        raise ArticleNotFound(f"No Article node in schema graph for {url} -- not an article page.")

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
        "commentCount": article.get("commentCount"),
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
        raise UnexpectedShape("No <url> elements found in the Google News sitemap -- sitemap shape has likely changed.")

    results = []
    for url_node in url_nodes:
        loc = url_node.find("loc")
        link = loc.text.strip() if loc and loc.text else None
        if not link:
            continue
        title_tag = url_node.find("news:title")
        pub_date_tag = url_node.find("news:publication_date")
        keywords_tag = url_node.find("news:keywords")
        image_tag = url_node.find("image:loc")
        title = html.unescape(title_tag.text.strip()) if title_tag and title_tag.text else None
        pub_date = pub_date_tag.text.strip() if pub_date_tag and pub_date_tag.text else None
        keywords = keywords_tag.text.strip() if keywords_tag and keywords_tag.text else None
        image = image_tag.text.strip() if image_tag and image_tag.text else None
        results.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title,
                "link": link,
                "pubDate": pub_date,
                "keywords": keywords,
                "image": image,
            }
        )

    # Confirmed newest-first in file order on every sample taken, but sort
    # descending by publication date defensively anyway.
    results.sort(key=lambda r: r["pubDate"] or "", reverse=True)
    return results
