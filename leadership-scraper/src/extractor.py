"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- leadership.ng (LEADERSHIP Newspapers, WordPress +
             Rank Math / custom SEO plugin) emits ONE `<script
             type="application/ld+json">` block per article page, a Yoast-
             style `@graph` array of cross-referenced nodes (`Article`,
             `NewsMediaOrganization`/`Organization`, `WebSite`,
             `ImageObject`, `BreadcrumbList`, `WebPage`). Unlike
             premiumtimesng.com/punchng.com, the `Article` node's `author`
             field is an INLINE object (`{"@type":"Person","name":"..."}`),
             not a bare `{"@id": "..."}` reference -- no author-node
             resolution round-trip is strictly required, but the same
             `@id`-resolving helper is reused anyway for robustness. The
             `publisher` and `image` fields ARE bare `{"@id": "..."}`
             references that must be resolved against sibling nodes in the
             same `@graph` (an `Organization` node for publisher, an
             `ImageObject` node for image). There is **no `thumbnailUrl`,
             `wordCount`, or `commentCount`** field anywhere in the graph on
             this site (confirmed absent across 3 sampled articles spanning
             News/Entertainment/Business) -- `image` (resolved from the
             `ImageObject` node's `url`) is used instead of `thumbnailUrl`.
             `keywords` is present on some articles and absent on others
             (a single string, e.g. `"Davido"`, never a list); `articleSection`
             is always a single string (e.g. `"News"`, `"Business"`), never
             a list, unlike premiumtimesng.com/punchng.com.
             Text values inside this JSON are proper JSON-Unicode-escaped
             (e.g. `"Ogogo\\u2019s"` decodes correctly via plain `json.loads`)
             -- NOT double-HTML-escaped like premiumtimesng.com's
             `&#8217;`-in-a-JSON-string pattern. `html.unescape()` is still
             applied to every text value pulled from the graph as a no-op
             safety net, for robustness against a future shape change.
             Full body text comes from HTML: `div.entry-content >
             div.content-inner`, direct-child `<p>` tags only
             (`recursive=False`) -- confirmed this selector matches exactly
             ONE element per article page; ad slots (`div.code-block-N`,
             Google Publisher Tag containers) and the floating share bar
             (`div.jeg_share_button`) are sibling `<div>` elements at that
             same level, excluded automatically without a denylist.
             A deleted/never-existed slug 200-OKs to the **homepage**
             instead of a real 404 (soft-404, same pattern as
             premiumtimesng.com) -- but unlike premiumtimesng.com, the
             homepage's OWN `@graph` also carries an `Article` node (it
             describes the front page itself: headline = site title,
             author name `"Web"`), so "no Article node" is NOT a reliable
             soft-404 signal here. The real tell: the Article node's
             `mainEntityOfPage` resolves to a `WebPage` node whose own
             `url` field is the homepage (`https://leadership.ng/`), not
             the requested article URL -- checked explicitly and reported
             as `_error: "not_found"`.
  S2-rss   -- `/feed/` (WordPress default feed). Each `<item>` carries
             `title`, `link`, `dc:creator` (a REAL per-article byline that
             matches the ld+json `author.name` -- not a generic placeholder
             like punchng.com's constant `"Punch Newspapers"`), `pubDate`,
             a single `<category>`, a `guid`, a teaser `description` (plain
             text inside CDATA, HTML-entity-escaped, ending in a
             "... [&#8230;]" truncation marker -- no "appeared first on ..."
             boilerplate, unlike premiumtimesng.com), and -- unusually for
             a "latest" feed on this portfolio -- a full-text
             `<content:encoded>` block with the complete article HTML. That
             full HTML is passed through raw as `content`, plus a flattened
             plain-text `articleBody` convenience field (paragraphs joined),
             so `latest` mode already carries the full story without a
             second `article`-mode request. Confirmed paginable via
             `?paged=N` (10 items per page, no overlap between pages,
             checked across 2 consecutive pages) with no `<enclosure>` or
             `media:thumbnail` tag on this feed, so no per-item lead image
             is available in latest mode.
"""

import html
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


class ArticleNotFound(Exception):
    """A deleted/never-existed article slug resolves as a soft-404 (HTTP
    200, homepage content, no Article node in the schema graph) -- an
    expected per-input failure, not a schema-drift crash. See
    CRAWLING_METHOD.md.
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


def _urls_match(a: str, b: str) -> bool:
    return a.rstrip("/").lower() == b.rstrip("/").lower()


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
        raise UnexpectedShape("No @graph ld+json block found -- page shape has likely changed.")

    article = _find_node(graph, {"Article", "NewsArticle"})
    if article is None:
        # Deleted/never-existed slugs 200-OK to the homepage instead of a
        # real 404 -- no Article node in the graph is the tell.
        raise ArticleNotFound(f"No Article node in schema graph for {url} -- soft-404 (homepage fallback).")

    index = _index_graph(graph)

    # The homepage ITSELF carries an Article node describing the front page
    # (headline = site title, author name "Web") -- so presence of an
    # Article node alone doesn't prove this is a real article page. The
    # real soft-404 tell is that the Article's mainEntityOfPage resolves to
    # a WebPage node whose own `url` is the homepage, not the requested
    # article URL. See CRAWLING_METHOD.md.
    webpage_nodes = _resolve_refs(article.get("mainEntityOfPage"), index)
    webpage_url = webpage_nodes[0].get("url") if webpage_nodes and webpage_nodes[0].get("url") else None
    if webpage_url and not _urls_match(webpage_url, url):
        raise ArticleNotFound(
            f"Schema graph's WebPage.url ({webpage_url}) doesn't match requested url ({url}) -- soft-404 (homepage fallback)."
        )

    author_nodes = _resolve_refs(article.get("author"), index)
    author_names = [html.unescape(n["name"]) for n in author_nodes if n.get("name")]

    publisher_nodes = _resolve_refs(article.get("publisher"), index)
    publisher_name = html.unescape(publisher_nodes[0]["name"]) if publisher_nodes and publisher_nodes[0].get("name") else None

    image_nodes = _resolve_refs(article.get("image"), index)
    image_url = image_nodes[0].get("url") if image_nodes else None

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
        "dateModified": article.get("dateModified"),
        "image": image_url,
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def _flatten_html(raw_html: str | None) -> str | None:
    """RSS content:encoded is raw WordPress HTML (<p>, ad-slot <div>s,
    etc). Join direct-child paragraph text into a plain-text convenience
    field, same approach as extract_article's HTML-mode body extraction."""
    if not raw_html:
        return None
    soup = BeautifulSoup(raw_html, "lxml")
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
    return "\n\n".join(paragraphs) or None


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
        content_encoded = item.find("encoded")  # content:encoded
        pub_date = item.find("pubDate")
        categories = [c.text.strip() for c in item.find_all("category") if c.text and c.text.strip()]
        creator = item.find("dc:creator") or item.find("creator") or item.find("author")
        guid = item.find("guid")
        description = html.unescape(description_tag.text).strip() if description_tag and description_tag.text else None
        content_text = content_encoded.text if content_encoded and content_encoded.text else None
        results.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "description": description,
                "content": content_text,
                "articleBody": _flatten_html(content_text),
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "categories": categories or None,
                "author": creator.text.strip() if creator and creator.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
            }
        )
    return results
