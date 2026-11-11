"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- premiumtimesng.com (WordPress + Yoast SEO) emits ONE
             `<script type="application/ld+json" class="yoast-schema-graph">`
             block per article page, wrapping a Yoast-style `@graph` array
             of cross-referenced nodes (`Article`, `WebPage`, `ImageObject`,
             `BreadcrumbList`, `WebSite`, `Organization`, `Person`) --
             `@type` is `Article`, not `NewsArticle`. The `Article` node
             carries `headline`, `datePublished`, `wordCount`,
             `commentCount`, `keywords`, `articleSection`, `thumbnailUrl`,
             but **no `articleBody`**, and `author`/`publisher`/`image` are
             all `{"@id": "..."}` references that must be resolved against
             sibling nodes in the same `@graph` array (the `Person` node
             carries the real byline `name`; the `Organization` node
             carries the publisher `name`, always `"Premium Times"`).
             There is no `dateModified` anywhere in the graph -- confirmed
             absent on every sampled article, not just omitted here.
             WordPress double-HTML-escapes text values inside this JSON
             (e.g. `"Sultan Sa&#8217;ad Abubakar III"` as literal JSON
             string content, not real Unicode) -- `html.unescape()` is
             applied to every text value pulled out of the graph
             (headline, keywords, articleSection, author/publisher names).
             Full body text comes from HTML instead:
             `div.entry-content > div.content-inner`, direct-child `<p>`
             tags only. Ad slots (`div.code-block-N`, Ad Inserter
             `div.ai-viewports`), the floating share button bar
             (`div.jeg_share_button`), the lead image `<figure>`, and the
             end-of-article "Share this" / "Discover more" / tags widgets
             are all sibling `<div>`/`<figure>` elements at that same
             level, not `<p>` tags, so a `recursive=False` scan for `<p>`
             excludes them automatically without a denylist.
             `description` is pulled from `<meta name="description">`
             (falls back to the `WebPage` node's own `description` field,
             also confirmed present on every sample, if the meta tag is
             ever missing).
  S2-rss   -- `/feed` (WordPress default feed, confirmed **not** paginated
             beyond `?paged=N` -- each page holds exactly 15 items, no
             `content:encoded` full-text field). `description` is raw,
             once-HTML-escaped HTML text inside a CDATA block (a lead
             `<img>` tag + teaser `<p>` + literal "The post ... appeared
             first on Premium Times Nigeria." boilerplate) -- cleaned with
             `html.unescape()` + tag-stripping, same pattern as
             `vice-scraper`. The lead image URL is pulled out of that same
             `<img src="...">` before the tags are stripped (there is no
             `<enclosure>` tag on this feed, unlike `kyivpost-scraper`).
"""

import html
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


class ArticleNotFound(Exception):
    """A deleted/never-existed article ID resolves as a soft-404 (HTTP 200,
    homepage content, no Article node in the schema graph) -- an expected
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
    container = soup.select_one("div.entry-content > div.content-inner")
    if container is None:
        raise UnexpectedShape("No div.entry-content > div.content-inner found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p", recursive=False) if p.get_text(strip=True)]
    return "\n\n".join(paragraphs)


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    graph = _find_schema_graph(soup)
    if graph is None:
        raise UnexpectedShape("No Yoast @graph ld+json block found -- page shape has likely changed.")

    article = _find_node(graph, {"Article", "NewsArticle"})
    if article is None:
        # Deleted/never-existed article IDs 200-OK to the homepage instead
        # of a real 404 -- no Article node in the graph is the tell.
        raise ArticleNotFound(f"No Article node in schema graph for {url} -- soft-404 (homepage fallback).")

    index = _index_graph(graph)

    author_nodes = _resolve_refs(article.get("author"), index)
    author_names = [html.unescape(n["name"]) for n in author_nodes if n.get("name")]

    publisher_nodes = _resolve_refs(article.get("publisher"), index)
    publisher_name = html.unescape(publisher_nodes[0]["name"]) if publisher_nodes and publisher_nodes[0].get("name") else None

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
        "keywords": _unescape(article.get("keywords")),
        "datePublished": article.get("datePublished"),
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


def _clean_description(raw: str | None) -> tuple[str | None, str | None]:
    """Returns (plain_text, lead_image_url)."""
    if not raw:
        return None, None
    unescaped = html.unescape(raw)
    soup = BeautifulSoup(unescaped, "lxml")
    img = soup.find("img")
    image_url = img.get("src") if img else None
    text = soup.get_text(" ", strip=True)
    return text or None, image_url


def extract_rss_items(xml_text: str) -> list[dict]:
    soup = BeautifulSoup(xml_text, "xml")
    items = soup.find_all("item")
    if not items:
        raise UnexpectedShape("No <item> elements found in RSS feed -- feed shape has likely changed.")
    results = []
    for item in items:
        title = item.find("title")
        link = item.find("link")
        description_tag = item.find("description")
        pub_date = item.find("pubDate")
        categories = [c.text.strip() for c in item.find_all("category") if c.text]
        creator = item.find("dc:creator") or item.find("creator") or item.find("author")
        guid = item.find("guid")
        description, image_url = _clean_description(description_tag.text if description_tag else None)
        results.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "description": description,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "categories": categories or None,
                "author": creator.text.strip() if creator and creator.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "image": image_url,
            }
        )
    return results
