"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- freepresskashmir.news (WordPress + All in One SEO v4.9.9)
             emits ONE `<script type="application/ld+json" class="aioseo-
             schema">` block per article page, an AIOSEO-style `@graph`
             array of cross-referenced nodes (`Article`, `BreadcrumbList`,
             `Organization`, `Person`, `WebPage`, `WebSite`). The `Article`
             node carries `headline`/`name`, `datePublished`, `dateModified`,
             `articleSection` (a single comma-separated string of categories
             + tags, not an array), `image` -- but **no `articleBody`**.
             Both `author` and `publisher` are bare `{"@id": ...}`
             references (never inlined on the `Article` node itself) that
             resolve against the graph's own `Person` (byline -- a named
             reporter, e.g. "Al-Misda Masoom", or the "News Desk" credit) and
             `Organization` (`name: "Free Press Kashmir"`) nodes
             respectively. `html.unescape()` is applied to every text value
             pulled from the graph for robustness even though no double-
             escaping was observed on the 3 samples checked.
             Full body text comes from HTML: `div#content-main`, direct-
             child `<p>` tags only (`recursive=False`) -- confirmed this
             exact id appears exactly ONCE per article page; ad-slot `<div>`
             containers (randomly-named classes wrapping AdSense script
             tags) and the closing `div.mvp-related-posts` block sit as
             direct-child `<div>` siblings alongside the `<p>` tags inside
             the same container, so they're skipped automatically by the
             tag-name filter without needing extra scoping.
             A deliberately-invented slug returns a REAL HTTP 404 (confirmed
             on a probe) -- no soft-404 quirk observed.
  S2-rss    -- site-wide `/feed/` RSS 2.0 feed for `latest` mode.
               title/link/guid/pubDate/description/dc:creator/category,
               newest-first.
"""

import html
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


class ArticleNotFound(Exception):
    """The page 200-OK'd but is not an article (no Article node in the
    schema graph) -- e.g. a static page like /about-us/. An expected
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
    container = soup.select_one("div#content-main")
    if container is None:
        raise UnexpectedShape("No div#content-main found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p", recursive=False) if p.get_text(strip=True)]
    return "\n\n".join(paragraphs)


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    graph = _find_schema_graph(soup)
    if graph is None:
        raise UnexpectedShape("No AIOSEO @graph ld+json block found -- page shape has likely changed.")

    article = _find_node(graph, {"Article", "NewsArticle"})
    if article is None:
        # Non-article pages (e.g. /about-us/) 200-OK with a
        # WebPage/BreadcrumbList/WebSite/Organization graph and no
        # Article node.
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

    image_node = article.get("image")
    image_url = None
    if isinstance(image_node, dict):
        image_url = image_node.get("url")

    return {
        "_input": url,
        "_source": "S1-jsonld+html",
        "_scrapedAt": utc_now_iso(),
        "headline": _unescape(article.get("headline") or article.get("name")),
        "description": description,
        "articleBody": article_body,
        "author": ", ".join(author_names) if author_names else None,
        "publisher": publisher,
        "articleSection": _unescape(article.get("articleSection")),
        "image": image_url,
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_rss_items(xml_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    items = []
    for item in soup.find_all("item"):
        title = item.find("title")
        link = item.find("link")
        guid = item.find("guid")
        pub_date = item.find("pubDate")
        description = item.find("description")
        creator = item.find("creator")
        category = item.find("category")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": html.unescape(title.text.strip()) if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "description": html.unescape(description.text.strip()) if description and description.text and description.text.strip() else None,
                "author": creator.text.strip() if creator and creator.text else None,
                "category": category.text.strip() if category and category.text else None,
            }
        )
    if not items:
        raise UnexpectedShape("No <item> elements found in RSS feed -- feed shape has likely changed.")
    return items
