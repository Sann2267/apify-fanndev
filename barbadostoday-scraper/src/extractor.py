"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-wpapi       -- barbadostoday.bb (WordPress, Yoast SEO, Penci theme)
                     exposes its standard, unauthenticated REST API at
                     `/wp-json/wp/v2/posts`. Given only an article URL, the
                     slug (the URL's last path segment) is queried via
                     `?slug=<slug>&_embed=1`, which returns the full post in
                     ONE round trip -- `content.rendered` (the complete
                     article body), `excerpt.rendered` (a short teaser),
                     plus the embedded real author name, featured-media
                     object, and category/tag term objects. This is the
                     primary strategy for BOTH article mode and latest mode
                     (`?per_page=<limit>&_embed=1`, no `slug` filter) --
                     confirmed `per_page` up to 50 works in a single call,
                     no pagination loop needed. Chosen over the site's own
                     working `/feed/` RSS because it returns the exact same
                     rich shape (full body, real author, categories/tags)
                     for latest mode too, not a thin title/link/pubDate
                     shape.
  S2-jsonld+html -- fallback used only if the REST API call itself fails
                     (non-200/timeout) after retries. The article HTML
                     carries ONE `<script type="application/ld+json">`
                     block -- a Yoast-style `@graph` array of 7
                     cross-referenced nodes (`Article`, `WebPage`,
                     `ImageObject`, `BreadcrumbList`, `WebSite`,
                     `Organization`, `Person`). `Article.author` is a bare
                     `{"@id": "...#/schema/person/<hash>"}` reference that
                     resolves against the graph's own `Person` node (real
                     name, e.g. "Shanna Moore"); `Article.publisher` is
                     likewise a bare `{"@id": "...#organization"}` reference
                     resolving to the graph's `Organization` node
                     (`name: "Barbados Today Inc"`). The `Article` node
                     carries `headline`, `datePublished`, `dateModified`,
                     `wordCount`, `keywords`, `articleSection` -- but no
                     `articleBody`. Full body text comes from HTML:
                     `div.entry-content`, direct-child `<p>` tags only
                     (`recursive=False`) -- confirmed this class appears
                     exactly ONCE per article page with 29/29 direct-vs-total
                     `<p>` tags (no nested ad/related paragraphs to filter
                     out). A page that 200-OKs but is not an article (e.g. a
                     static page) emits a graph with no `Article` node --
                     detected explicitly and reported as `_error:
                     "not_article"` rather than a schema-drift crash.
"""

import html
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


class ArticleNotFound(Exception):
    """The page 200-OK'd but is not an article (no Article/NewsArticle node
    in the schema graph) -- an expected per-input failure, not a schema-
    drift crash. See CRAWLING_METHOD.md.
    """


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_html_text(raw: str | None) -> str | None:
    """Single-block text (title, excerpt): unescape, strip tags, collapse whitespace."""
    if raw is None:
        return None
    unescaped = html.unescape(raw)
    text = BeautifulSoup(unescaped, "lxml").get_text(" ", strip=True)
    return text or None


def _paragraphs_from_html(raw: str | None) -> str | None:
    """Multi-paragraph body: join each <p> as its own line, blank line between."""
    if not raw or not raw.strip():
        return None
    soup = BeautifulSoup(html.unescape(raw), "lxml")
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
    return "\n\n".join(paragraphs) if paragraphs else None


def extract_article_wpapi(post: dict, input_value: str) -> dict:
    """S1-wpapi -- parse one item from /wp-json/wp/v2/posts (article or latest mode)."""
    if "content" not in post or "rendered" not in post.get("content", {}):
        raise UnexpectedShape(f"WP API post is missing content.rendered -- got keys={list(post.keys())}")

    embedded = post.get("_embedded") or {}

    author_obj = (embedded.get("author") or [{}])[0]
    author_name = author_obj.get("name")
    author_slug = author_obj.get("slug")
    author_link = author_obj.get("link")

    media_list = embedded.get("wp:featuredmedia") or []
    media_obj = media_list[0] if media_list and not media_list[0].get("code") else None
    featured_image = None
    if media_obj:
        details = media_obj.get("media_details") or {}
        featured_image = {
            "url": media_obj.get("source_url"),
            "width": details.get("width"),
            "height": details.get("height"),
            "altText": media_obj.get("alt_text") or None,
        }

    categories: list[str] = []
    tags: list[str] = []
    for group in embedded.get("wp:term") or []:
        for term in group:
            if not isinstance(term, dict):
                continue
            if term.get("taxonomy") == "category":
                categories.append(term.get("name"))
            elif term.get("taxonomy") == "post_tag":
                tags.append(term.get("name"))

    content = post.get("content") or {}
    excerpt = post.get("excerpt") or {}

    return {
        "_input": input_value,
        "_source": "S1-wpapi",
        "_scrapedAt": utc_now_iso(),
        "id": post.get("id"),
        "slug": post.get("slug"),
        "link": post.get("link"),
        "headline": _clean_html_text((post.get("title") or {}).get("rendered")),
        "description": _clean_html_text(excerpt.get("rendered")),
        "articleBody": _paragraphs_from_html(content.get("rendered")),
        "date": post.get("date"),
        "date_gmt": post.get("date_gmt"),
        "modified": post.get("modified"),
        "modified_gmt": post.get("modified_gmt"),
        "author": author_name,
        "authorSlug": author_slug,
        "authorLink": author_link,
        "categories": categories,
        "tags": tags,
        "featuredImage": featured_image,
        "guid": (post.get("guid") or {}).get("rendered"),
        "contentProtected": content.get("protected"),
    }


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


def _extract_body_html(soup: BeautifulSoup) -> str:
    container = soup.select_one("div.entry-content")
    if container is None:
        raise UnexpectedShape("No div.entry-content found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p", recursive=False) if p.get_text(strip=True)]
    return "\n\n".join(paragraphs)


def extract_article_html_fallback(html_text: str, url: str) -> dict:
    """S2-jsonld+html -- used only when the WP REST API call itself fails."""
    soup = BeautifulSoup(html_text, "lxml")

    graph = _find_schema_graph(soup)
    if graph is None:
        raise UnexpectedShape("No Yoast @graph ld+json block found -- page shape has likely changed.")

    article = _find_node(graph, {"Article", "NewsArticle"})
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

    article_body = _extract_body_html(soup)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    description = meta_desc_tag.get("content") if meta_desc_tag else None

    return {
        "_input": url,
        "_source": "S2-jsonld+html",
        "_scrapedAt": utc_now_iso(),
        "headline": html.unescape(article.get("headline")) if article.get("headline") else None,
        "description": description,
        "articleBody": article_body,
        "author": ", ".join(author_names) if author_names else None,
        "publisher": publisher,
        "articleSection": article.get("articleSection"),
        "keywords": article.get("keywords"),
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
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
