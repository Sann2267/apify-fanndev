"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- organiser.org (WordPress + JNews theme, Rank-Math-style
             SEO plugin) emits ONE `<script type="application/ld+json">`
             block per article page, wrapping a `@graph` array of
             cross-referenced nodes (`NewsArticle`, `WebPage`, `ImageObject`,
             `BreadcrumbList`, `WebSite`, `Organization`, `Person`). The
             `NewsArticle` node carries `headline`, `datePublished`,
             `wordCount`, `keywords`, `articleSection`, `thumbnailUrl`, but
             **no `articleBody`** and **no `dateModified`** (confirmed
             absent on every sampled article, not just omitted here).
             `author` is always a bare `{"@id": "..."}` reference that must
             be resolved against the sibling `Person` node in the same
             `@graph` array for the real byline name; `publisher` is
             likewise a bare `{"@id": "..."}` reference resolved against the
             `Organization` node.
             **Quirk:** `keywords` is a JSON *object* with sparse,
             non-contiguous string-integer keys (e.g.
             `{"2": "RSS", "3": "...", "5": "..."}`, first index sometimes
             `"0"`, sometimes `"2"`) instead of a JSON array -- passed
             through as-is (raw passthrough), not reshaped into a list.
             Full body text comes from HTML instead:
             `div.entry-content > div.content-inner`, direct-child `<p>`
             tags only (JNews theme). Ad slots and share-button widgets are
             sibling `<div>` elements at that same level, not `<p>` tags, so
             a `recursive=False` scan for `<p>` excludes them automatically.
             `description` is pulled from `<meta name="description">`
             (falls back to the `WebPage` node's own `description` field if
             the meta tag is ever missing).
  S2-rss    -- site-wide `/feed/` (WordPress default feed, paginated via
             `?paged=N`, confirmed live). Richer than a typical RSS 2.0
             feed: title/link/guid/pubDate/dc:creator/category (list) plus
             a full-HTML `content:encoded` body (~1.4x longer than
             `description`, confirmed via direct length comparison on a
             live sample) -- so `latest` mode already returns full article
             text, not just a teaser.
"""

import html
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


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
    container = soup.select_one("div.entry-content > div.content-inner")
    if container is None:
        raise UnexpectedShape("No div.entry-content > div.content-inner found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p", recursive=False) if p.get_text(strip=True)]
    return "\n\n".join(paragraphs)


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    graph = _find_schema_graph(soup)
    if graph is None:
        raise UnexpectedShape("No ld+json @graph block found -- page shape has likely changed.")

    article = _find_node(graph, {"NewsArticle", "Article"})
    if article is None:
        raise UnexpectedShape("No NewsArticle/Article node in schema graph -- page shape has likely changed.")

    index = _index_graph(graph)

    author_nodes = _resolve_refs(article.get("author"), index)
    author_names = [html.unescape(n["name"]) for n in author_nodes if n.get("name")]

    publisher_nodes = _resolve_refs(article.get("publisher"), index)
    publisher_name = html.unescape(publisher_nodes[0]["name"]) if publisher_nodes and publisher_nodes[0].get("name") else None

    image_nodes = _resolve_refs(article.get("image"), index)
    image_url = image_nodes[0].get("url") if image_nodes and image_nodes[0].get("url") else None

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
        "publisher": publisher_name,
        "articleSection": _unescape(article.get("articleSection")),
        "keywords": article.get("keywords"),
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "thumbnailUrl": article.get("thumbnailUrl"),
        "image": image_url,
        "wordCount": article.get("wordCount"),
        "inLanguage": article.get("inLanguage"),
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_rss_items(xml_text: str | bytes) -> list[dict]:
    soup = BeautifulSoup(xml_text, "xml")
    items = soup.find_all("item")
    if not items:
        raise UnexpectedShape("No <item> elements found in RSS feed -- feed shape has likely changed.")
    results = []
    for item in items:
        title = item.find("title")
        link = item.find("link")
        guid = item.find("guid")
        pub_date = item.find("pubDate")
        description = item.find("description")
        categories = [c.text.strip() for c in item.find_all("category") if c.text and c.text.strip()]
        # BeautifulSoup's "xml" (lxml-xml) parser strips namespace prefixes
        # from tag names, so dc:creator becomes findable as "creator" and
        # content:encoded as "encoded".
        creator = item.find("creator")
        content_encoded = item.find("encoded")
        results.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "description": description.text.strip() if description and description.text and description.text.strip() else None,
                "category": categories or None,
                "author": creator.text.strip() if creator and creator.text else None,
                "contentEncoded": content_encoded.text.strip() if content_encoded and content_encoded.text else None,
            }
        )
    return results
