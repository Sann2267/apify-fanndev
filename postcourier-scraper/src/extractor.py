"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+wpapi -- postcourier.com.pg (Post Courier, WordPress + Yoast SEO
             + WooCommerce Memberships) emits ONE
             `<script type="application/ld+json">` block per article page, a
             Yoast-style `@graph` array of cross-referenced nodes (`Article`,
             `WebPage`, `ImageObject`, `BreadcrumbList`, `WebSite`,
             `Organization`, `Person`). The `Article` node carries
             `headline`, `datePublished`, `dateModified`, `wordCount`,
             `keywords`, `articleSection`, `thumbnailUrl` -- but no
             `articleBody`. `author` shape is INCONSISTENT across samples:
             sometimes a list of `{"@id": ...}` refs, sometimes a single
             inline `{"name": ..., "@id": ...}` dict -- `_resolve_refs`
             normalizes both. `publisher` is a bare
             `{"@id": "...#organization"}` ref that resolves to a real
             `Organization` node (`name: "Post Courier"`) in the same graph.
             Full body text (and paywall status) comes from the WordPress
             REST API instead of HTML scraping: `GET /wp-json/wp/v2/posts
             ?slug=<slug>&_embed=1` returns `content.rendered` (clean HTML
             fragment, no ads/nav to filter), plus embedded author name,
             featured-media URL, and category/tag term names via
             `_embedded`.
             **Hard paywall (WooCommerce Memberships):** a paywalled post's
             `content.rendered` contains only a `div.content-preview`
             teaser (~2 paragraphs) followed by a
             `div.wc-memberships-restriction-message` upsell block instead
             of the real body. Detected by that CSS class string; when
             present, `articleBody` is limited to the paragraphs inside
             `div.content-preview` and `_paywalled` is set `True`. Free
             articles (mostly PACNEWS wire content tagged "World"/"World
             News") have no such wrapper -- every `<p>` in `content.rendered`
             is used and `_paywalled` is `False`.
             A genuinely deleted/never-existed slug returns a REAL HTTP 404
             on the article HTML page (confirmed on a deliberately-invented
             slug) -- no soft-404 quirk observed. A quirk NOT worth working
             around: some article text uses the same left-curly-quote
             character (U+201C) for both the opening AND closing quote mark
             around a phrase (e.g. `“serious”` appears in the
             source as `“serious“`) -- a genuine upstream
             authoring inconsistency, passed through verbatim per the
             raw-passthrough convention, not a decoding bug in this actor
             (independently confirmed via raw-byte + codepoint inspection).
             No `<meta name="description">` tag was found on any sampled
             article page, and the graph's `WebPage` node carries no
             `description` field either -- `description` falls back to
             `<meta property="og:description">`, which was populated on
             every sample.
  S2-rss     -- `/feed/` (standard WordPress RSS2 feed) is live and populated
             (confirmed HTTP 200, non-empty `<item>` list) -- unlike some
             other small regional-daily actors in this portfolio where
             RSS/sitemap is broken and a homepage-link-scrape fallback is
             required, that fallback was NOT needed here. Each `<item>`
             carries `title`, `link`, `pubDate` (real per-article RFC-822
             timestamp), `dc:creator`, and one or more `<category>` tags.
             Confirmed already newest-first in feed order, but sorted
             descending by `pubDate` defensively anyway.
"""

import html
import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


class ArticleNotFound(Exception):
    """The page 200-OK'd but is not an article (no Article/NewsArticle node
    in the schema graph) -- e.g. a static page. An expected per-input
    failure, not a schema-drift crash.
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


def slug_from_url(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def _extract_body_and_paywall(content_html: str) -> tuple[str, bool]:
    soup = BeautifulSoup(content_html, "lxml")
    restriction = soup.select_one(".wc-memberships-restriction-message")
    paywalled = restriction is not None
    scope = soup.select_one("div.content-preview") if paywalled else soup
    if scope is None:
        scope = soup
    paragraphs = [p.get_text(" ", strip=True) for p in scope.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    return "\n\n".join(paragraphs), paywalled


def extract_article(html_text: str, wp_post: dict | None, url: str) -> dict:
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

    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    description = meta_desc_tag.get("content") if meta_desc_tag else None
    if not description:
        webpage = _find_node(graph, {"WebPage"})
        description = webpage.get("description") if webpage else None
    if not description:
        # No <meta name="description"> and no WebPage.description observed
        # on this site's article pages -- og:description is populated
        # instead (confirmed on every sampled article).
        og_desc_tag = soup.find("meta", attrs={"property": "og:description"})
        description = og_desc_tag.get("content") if og_desc_tag else None

    record = {
        "_input": url,
        "_source": "S1-jsonld+wpapi",
        "_scrapedAt": utc_now_iso(),
        "headline": _unescape(article.get("headline")),
        "description": description,
        "author": ", ".join(author_names) if author_names else None,
        "publisher": publisher,
        "articleSection": _unescape(article.get("articleSection")),
        "keywords": _unescape(article.get("keywords")),
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "thumbnailUrl": article.get("thumbnailUrl"),
        "wordCount": article.get("wordCount"),
    }

    if wp_post is None:
        # WP REST API lookup by slug came back empty even though the HTML
        # page itself 200-OK'd with a valid Article node -- degrade rather
        # than crash the whole run (rare; not observed in recon sampling).
        record["articleBody"] = None
        record["_paywalled"] = None
        record["_warning"] = "wp_api_post_not_found"
        return record

    content_html = wp_post.get("content", {}).get("rendered", "")
    article_body, paywalled = _extract_body_and_paywall(content_html)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    embedded = wp_post.get("_embedded", {}) or {}
    wp_author = None
    for a in embedded.get("author", []) or []:
        if a.get("name"):
            wp_author = a["name"]
            break

    featured_media_url = None
    for m in embedded.get("wp:featuredmedia", []) or []:
        if m.get("source_url"):
            featured_media_url = m["source_url"]
            break

    categories, tags = [], []
    for group in embedded.get("wp:term", []) or []:
        for term in group:
            if term.get("taxonomy") == "category" and term.get("name"):
                categories.append(term["name"])
            elif term.get("taxonomy") == "post_tag" and term.get("name"):
                tags.append(term["name"])

    record.update(
        {
            "articleBody": article_body,
            "_paywalled": paywalled,
            "wpAuthor": wp_author,
            "featuredMediaUrl": featured_media_url,
            "categories": categories or None,
            "tags": tags or None,
            "coauthors": wp_post.get("coauthors"),
        }
    )
    return record


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
    item_nodes = soup.find_all("item")
    if not item_nodes:
        raise UnexpectedShape("No <item> elements found in RSS feed -- feed shape has likely changed.")

    results = []
    for item in item_nodes:
        title_tag = item.find("title")
        link_tag = item.find("link")
        pub_date_tag = item.find("pubDate")
        creator_tag = item.find("dc:creator") or item.find("creator")
        categories = [c.text.strip() for c in item.find_all("category") if c.text and c.text.strip()]

        title = html.unescape(title_tag.text.strip()) if title_tag and title_tag.text else None
        link = link_tag.text.strip() if link_tag and link_tag.text else None
        pub_date_raw = pub_date_tag.text.strip() if pub_date_tag and pub_date_tag.text else None
        creator = html.unescape(creator_tag.text.strip()) if creator_tag and creator_tag.text else None

        pub_date_iso = None
        if pub_date_raw:
            try:
                pub_date_iso = parsedate_to_datetime(pub_date_raw).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except (TypeError, ValueError):
                pub_date_iso = None

        if not link:
            continue

        results.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title,
                "link": link,
                "pubDate": pub_date_raw,
                "pubDateIso": pub_date_iso,
                "creator": creator,
                "categories": categories or None,
            }
        )

    # Confirmed already newest-first in feed order, but sort descending by
    # the parsed ISO date defensively anyway (falls back to raw string sort
    # if parsing ever fails across the board).
    results.sort(key=lambda r: r["pubDateIso"] or r["pubDate"] or "", reverse=True)
    return results
