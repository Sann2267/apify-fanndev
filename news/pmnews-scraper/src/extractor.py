"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- pmnewsnigeria.com (WordPress + Yoast SEO) emits ONE
             `<script type="application/ld+json" class="yoast-schema-graph">`
             block per article page, a Yoast-style `@graph` array of
             cross-referenced nodes. The article node's `@type` is
             `"Article"` (NOT `"NewsArticle"` -- unlike most other WordPress
             outlets in this portfolio), so the node-type matcher checks
             both `{"NewsArticle", "Article"}`. The article node carries
             `headline`, `datePublished`, `wordCount`, `keywords`,
             `articleSection`, `thumbnailUrl`, an inline `author` object
             (`{"name": ..., "@id": ...}` -- name already present, no
             `Person`-node round-trip strictly required) -- but **no
             `articleBody`**, same gap as `punch-scraper`/
             `guardian-nigeria-scraper`.
             There is NO `Organization`/`publisher` node in the graph, AND
             NO `og:site_name` meta tag on this site either (both absent on
             every sampled article, unlike Punch which has the meta tag) --
             `publisher` is instead read from the graph's own `WebSite` node
             `name` field (`"P.M. News"`), which IS present and reliable.
             Quirk: the `WebSite`/`isPartOf` `@id` and the author `@id` both
             point at a raw origin-server IP (`http://34.243.69.150/...`)
             instead of the public domain -- a backend `siteurl`
             misconfiguration that doesn't affect extraction since only
             `.name` fields are read off these nodes, never the `@id` URLs.
             Full body text comes from HTML: `div.article_body`, direct-child
             `<p>` tags only (`recursive=False`) -- confirmed present with
             this exact class across 6 sampled articles spanning
             News/Politics/Metro/Sports/Entertainment.
             This site also has a bonus lead-in box not seen elsewhere in
             this portfolio: `div.quick_summary_box` (an `<h4>Quick Read</h4>`
             label followed by one `<p>` of AI/editor-written summary text),
             confirmed present on all 6 sampled articles -- captured as
             `quickSummary` (the `<p>` text only, label excluded).
             Quirk: the article node's `author.name` is the WordPress
             *publishing account* (e.g. "Ayorinde Oluokun", a desk editor),
             NOT necessarily the real reporter -- the real byline is often
             embedded as the article body's own first line ("By <Reporter
             Name>"), which is left untouched inside `articleBody` (raw
             passthrough, not parsed out as a separate field) since it's
             genuine article content, not boilerplate.
             A page that 200-OKs but is not an article (e.g. `/privacy-
             policy/`, `/contact-us/`) emits a `WebPage`/`BreadcrumbList`/
             `WebSite` graph with no `Article` node -- detected explicitly
             and reported as `_error: "not_article"` rather than a
             schema-drift crash. A genuinely deleted/never-existed slug
             returns a REAL HTTP 404 (confirmed on a deliberately-invented
             slug; the WP REST API independently confirms this too, 200 with
             an empty `[]`) -- no soft-404 quirk on this site.
  S2-rss   -- `/feed/` (stock WordPress feed). Each `<item>` carries `title`,
             `link`, `pubDate`, `dc:creator` (a REAL per-article byline that
             varies article-to-article -- unlike Punch's constant generic
             value), one or more `<category>` tags (REAL section/tag values,
             unlike Punch's always-empty tag), a `guid` using the
             `?p=<id>` query-string format (NOT the same as `link`), and a
             teaser `description` (plain text, matching the article page's
             own `quickSummary` content). No `<enclosure>` tag on this feed
             (unlike Punch) -- no `enclosureUrl` field is emitted here.
"""

import html
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


class ArticleNotFound(Exception):
    """The page 200-OK'd but is not an article (no Article node in the
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
    container = soup.select_one("div.article_body")
    if container is None:
        raise UnexpectedShape("No div.article_body found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p", recursive=False) if p.get_text(strip=True)]
    return "\n\n".join(paragraphs)


def _extract_quick_summary(soup: BeautifulSoup) -> str | None:
    container = soup.select_one("div.quick_summary_box")
    if container is None:
        return None
    p = container.find("p")
    text = p.get_text(" ", strip=True) if p else None
    return text or None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    graph = _find_schema_graph(soup)
    if graph is None:
        raise UnexpectedShape("No Yoast @graph ld+json block found -- page shape has likely changed.")

    article = _find_node(graph, {"NewsArticle", "Article"})
    if article is None:
        # Non-article pages (e.g. /privacy-policy/, /contact-us/) 200-OK with
        # a WebPage/BreadcrumbList/WebSite graph and no Article node.
        raise ArticleNotFound(f"No Article node in schema graph for {url} -- not an article page.")

    index = _index_graph(graph)

    author_nodes = _resolve_refs(article.get("author"), index)
    author_names = [html.unescape(n["name"]) for n in author_nodes if n.get("name")]

    website = _find_node(graph, {"WebSite"})
    publisher = html.unescape(website["name"]) if website and website.get("name") else None

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
        "quickSummary": _extract_quick_summary(soup),
        "articleBody": article_body,
        "author": ", ".join(author_names) if author_names else None,
        "publisher": publisher,
        "articleSection": _unescape(article.get("articleSection")),
        "keywords": _unescape(article.get("keywords")),
        "datePublished": article.get("datePublished"),
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
        categories = [c.text.strip() for c in item.find_all("category") if c.text and c.text.strip()]
        creator = item.find("dc:creator") or item.find("creator") or item.find("author")
        guid = item.find("guid")
        description = html.unescape(description_tag.text).strip() if description_tag and description_tag.text else None
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
            }
        )
    return results
