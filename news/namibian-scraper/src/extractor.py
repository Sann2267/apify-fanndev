"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html -- namibian.com.na (WordPress + Yoast SEO) emits one ld+json
             `@graph` array per article page holding an `Article` node,
             a `WebPage` node, a `BreadcrumbList` node, an `ImageObject`
             node and a `Person` node (or several, for multi-byline
             pieces). Like ghanaweb-scraper's `NewsArticle` node, the
             `Article` node carries `headline`, `datePublished`/
             `dateModified`, `articleSection` (list of WP category
             names, not a single clean string -- e.g.
             `["National","News","Top Story 1"]`), `wordCount`,
             `thumbnailUrl` -- but **no `articleBody`**, and `author`/
             `image` are `@id` *references* into the same `@graph`
             rather than inline objects (unlike GhanaWeb, where `author`
             is inline). The extractor builds an `@id` -> node lookup
             from the whole graph and resolves both. `author` resolves
             to a `Person` node with a plain `name` -- this holds for
             both staff-written pieces (byline is a real reporter, e.g.
             "Chris Kaukemua") *and* wire-service pieces (the `Person`
             node's `name` is the wire service itself, e.g. "AFP" --
             there is no separate "staff vs wire" signal in ld+json the
             way GhanaWeb has `noBylinesPolicy`; cross-reference RSS
             `<dc:creator>` if that distinction matters downstream).
             Full text comes from HTML: `div.entry-content` (WordPress
             Gutenberg block markup -- real `<p class="wp-block-
             paragraph">` tags, not a GhanaWeb/Global-Times single-`<p>`-
             with-`<br>` blob). Paragraphs are joined with a blank line.
             No trailing signature/promo line was found on staff or wire
             pieces (unlike GhanaWeb's reporter-initials quirk) -- the
             full paragraph list is the real body as-is.
  S2-rss  -- WordPress default feed (`/feed/`), advertised nowhere in
             robots.txt but not disallowed either. Paginates via
             `?paged=N`, 12 items/page. Carries `title`, `link`,
             `dc:creator`, `pubDate` (RFC-822), `category` (first WP
             category only -- WordPress RSS emits one `<category>` per
             assigned term but this feed is observed with exactly one
             per item), `guid`, `description` (short excerpt, HTML-
             entity-encoded, ends in "[&#8230;]" then a "the post ...
             appeared first on The Namibian" boilerplate paragraph) and
             **`content:encoded` -- the full article body HTML**, one
             quirk this actor takes advantage of: latest-mode records
             carry the complete article text with zero extra per-item
             HTTP calls, unlike GhanaWeb's Google News sitemap (headline
             metadata only). The trailing "The post ... appeared first
             on The Namibian." boilerplate paragraph WordPress appends to
             every `content:encoded` block is stripped before joining
             paragraphs, matched by a plain string check rather than a
             regex since the wording is fixed WordPress boilerplate.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

ARTICLE_ID_RE = re.compile(r"/([a-z0-9-]+)/?$")


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_slug(url: str) -> str | None:
    m = ARTICLE_ID_RE.search(url.split("?")[0])
    return m.group(1) if m else None


def _build_id_map(graph: list) -> dict:
    return {node["@id"]: node for node in graph if isinstance(node, dict) and "@id" in node}


def _find_node(graph: list, type_name: str) -> dict | None:
    for node in graph:
        if isinstance(node, dict) and node.get("@type") == type_name:
            return node
    return None


def _resolve_refs(value, id_map: dict):
    """Resolve one ref ({'@id': ...}) or a list of refs against id_map."""
    if isinstance(value, dict) and set(value.keys()) == {"@id"}:
        return id_map.get(value["@id"], value)
    if isinstance(value, list):
        return [_resolve_refs(v, id_map) for v in value]
    return value


def _extract_body(soup: BeautifulSoup) -> str:
    container = soup.select_one("div.entry-content")
    if container is None:
        raise UnexpectedShape("No div.entry-content element found -- page shape has likely changed.")

    paragraphs = [p.get_text(strip=True) for p in container.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    return "\n\n".join(paragraphs)


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article_body = _extract_body(soup)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    ld_tag = soup.find("script", attrs={"type": "application/ld+json"})
    if ld_tag is None or not ld_tag.string:
        raise UnexpectedShape("No ld+json block found -- page shape has likely changed.")
    try:
        data = json.loads(ld_tag.string)
    except json.JSONDecodeError as e:
        raise UnexpectedShape(f"ld+json block is not valid JSON: {e}") from e

    graph = data.get("@graph")
    if not isinstance(graph, list):
        raise UnexpectedShape("ld+json has no @graph array -- page shape has likely changed.")
    id_map = _build_id_map(graph)

    article = _find_node(graph, "Article")
    if article is None:
        raise UnexpectedShape("No Article ld+json node found -- page shape has likely changed.")

    authors = _resolve_refs(article.get("author"), id_map)
    author_names = None
    if isinstance(authors, list):
        author_names = [a.get("name") for a in authors if isinstance(a, dict) and a.get("name")]
        if len(author_names) == 1:
            author_names = author_names[0]
    elif isinstance(authors, dict):
        author_names = authors.get("name")

    image_node = _resolve_refs(article.get("image"), id_map)
    image = None
    if isinstance(image_node, dict):
        image = {
            "url": image_node.get("url"),
            "caption": image_node.get("caption"),
            "width": image_node.get("width"),
            "height": image_node.get("height"),
        }

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "slug": _extract_slug(url),
        "headline": article.get("headline"),
        "articleBody": article_body,
        "author": author_names,
        "category": article.get("articleSection"),
        "wordCount": article.get("wordCount"),
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "thumbnailUrl": article.get("thumbnailUrl"),
        "image": image,
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


_TRAILING_PROMO_MARKERS = ("The post ", "appeared first on")


def _clean_rss_content(html_fragment: str) -> str:
    soup = BeautifulSoup(html_fragment, "lxml")
    paragraphs = []
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if not text:
            continue
        # WordPress appends a fixed "The post <title> appeared first on
        # The Namibian." boilerplate paragraph to every content:encoded
        # block -- drop it, it's not part of the article.
        if all(m in text for m in _TRAILING_PROMO_MARKERS):
            continue
        paragraphs.append(text)
    return "\n\n".join(paragraphs)


def extract_rss_items(xml_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    items = soup.find_all("item")
    if not items:
        raise UnexpectedShape("No <item> elements found in RSS feed -- feed shape has likely changed.")

    results = []
    for item in items:
        link_el = item.find("link")
        link = link_el.text.strip() if link_el and link_el.text else None
        title_el = item.find("title")
        creator_el = item.find("creator")
        pub_date_el = item.find("pubDate")
        category_el = item.find("category")
        guid_el = item.find("guid")
        encoded_el = item.find("encoded")

        results.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "slug": _extract_slug(link) if link else None,
                "title": title_el.text.strip() if title_el and title_el.text else None,
                "link": link,
                "author": creator_el.text.strip() if creator_el and creator_el.text else None,
                "category": category_el.text.strip() if category_el and category_el.text else None,
                "pubDate": pub_date_el.text.strip() if pub_date_el and pub_date_el.text else None,
                "guid": guid_el.text.strip() if guid_el and guid_el.text else None,
                "content": _clean_rss_content(encoded_el.text) if encoded_el and encoded_el.text else None,
            }
        )
    return results
