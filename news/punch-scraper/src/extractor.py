"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- punchng.com (WordPress + Yoast SEO) emits ONE
             `<script type="application/ld+json" class="yoast-schema-graph">`
             block per article page, a Yoast-style `@graph` array of
             cross-referenced nodes (`NewsArticle`, `WebPage`, `ImageObject`,
             `BreadcrumbList`, `WebSite`, `Person`). Unlike some other
             Nigerian WordPress outlets in this portfolio (Premium Times),
             the `NewsArticle` node's `author` field is an INLINE object
             (`{"name": "...", "@id": "..."}`), not a bare `{"@id": "..."}`
             reference -- no author-node resolution round-trip is strictly
             required, but the same `@id`-resolving helper is reused anyway
             for robustness against a future shape change (e.g. a bare ref
             popping up), and it also uses the `Person` node to confirm the
             byline when present. There is NO `Organization`/`publisher`
             node anywhere in the graph on this site (confirmed absent
             across 4 sampled articles across News/Opinion/Metro Plus/
             Business sections) -- `publisher` is instead read from the
             `<meta property="og:site_name">` tag ("Punch Newspapers"),
             which is real page content, not fabricated.
             The `NewsArticle` node carries `headline`, `datePublished`,
             `dateModified`, `wordCount`, `keywords`, `articleSection`,
             `thumbnailUrl` -- but **no `articleBody`**. WordPress
             double-HTML-escapes text values inside this JSON (e.g.
             `"Business &amp; Economy"` as a literal JSON string, not a
             real `&`) -- `html.unescape()` is applied to every text value
             pulled from the graph (headline, keywords, articleSection,
             resolved author names).
             Full body text comes from HTML:
             `article.single-article div.post-content`, direct-child `<p>`
             tags only (`recursive=False`) -- confirmed this selector
             matches exactly ONE element per article page (related-article
             teaser cards elsewhere on the page also carry a bare
             `div.post-content` class, so the `article.single-article`
             ancestor scope is required to avoid picking up a teaser
             instead of the real body).
             A page that 200-OKs but is not an article at all (e.g.
             `/privacy-policy/`) emits a `WebPage`/`CollectionPage` graph
             with no `NewsArticle` node -- detected explicitly and reported
             as `_error: "not_article"` rather than a schema-drift crash.
             A genuinely deleted/never-existed slug returns a REAL HTTP 404
             (confirmed on a deliberately-invented slug) -- no soft-404
             quirk on this site, unlike premiumtimesng.com.
  S2-rss   -- `/feed` (WordPress-style feed served via rss.punchng.com,
             mirrored at punchng.com/feed). Each `<item>` carries `title`,
             `link` (with `?utm_source=rss.punchng.com&utm_medium=web`
             tracking params left on, passed through raw), `pubDate`,
             `dc:creator` (observed constant `"Punch Newspapers"` on every
             sampled item -- not a real per-article byline; use `article`
             mode against `link` for the real author), an always-empty
             `<category>` tag, a `guid`, and a teaser `description` (plain
             text inside CDATA, no embedded `<img>`, with a trailing
             "Read More: <url>" line appended -- real feed content, kept
             as-is). Every sampled item shares the exact same generic
             `<enclosure>` (the Punch masthead logo, not a per-article lead
             image) -- passed through raw as `enclosureUrl` since it is
             genuine feed content, but it is NOT a reliable per-article
             thumbnail (use `article` mode's `thumbnailUrl` for that).
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
    container = soup.select_one("article.single-article div.post-content")
    if container is None:
        raise UnexpectedShape("No article.single-article div.post-content found -- page shape has likely changed.")
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
        # WebPage/CollectionPage graph and no NewsArticle node.
        raise ArticleNotFound(f"No NewsArticle node in schema graph for {url} -- not an article page.")

    index = _index_graph(graph)

    author_nodes = _resolve_refs(article.get("author"), index)
    author_names = [html.unescape(n["name"]) for n in author_nodes if n.get("name")]

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
        enclosure = item.find("enclosure")
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
                "enclosureUrl": enclosure.get("url") if enclosure else None,
            }
        )
    return results
