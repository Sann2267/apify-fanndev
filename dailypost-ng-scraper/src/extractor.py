"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- dailypost.ng (Daily Post Nigeria, WordPress + Yoast SEO
             Premium v28.1) emits ONE `<script type="application/ld+json">`
             block per article page -- but UNLIKE Guardian Nigeria and Punch
             (also Yoast-powered, also in this portfolio), it is NOT a
             `@graph` array of cross-referenced nodes. It is a flat JSON
             array with a single item: `[{"@type": "NewsArticle", ...}]`.
             No `@id` refs to resolve, no graph indexing needed.
             Crucially, this node DOES carry a complete, untruncated
             `articleBody` (confirmed byte-for-byte length-equivalent
             against the HTML `#mvp-content-main` paragraph text on 3
             samples) -- Guardian Nigeria and Punch's graphs both omit
             `articleBody` entirely and require a separate HTML paragraph
             walk. That HTML walk is NOT needed here; JSON-LD alone is the
             primary and only strategy for article mode.
             Fields present: `headline`, `name` (duplicate of headline),
             `description`, `articleSection` (a plain string, e.g. "News"
             -- not a list like Guardian Nigeria's), `articleBody`,
             `keywords` (a list, sometimes with blank/whitespace-padded
             entries, e.g. `["nasarawa", " sule", " "]` -- passed through
             raw, not cleaned), `datePublished`, `dateModified`,
             `thumbnailUrl`, `wordCount`, `timeRequired` (ISO 8601
             duration, e.g. "PT28S"), `mainEntity` (a self-referencing
             WebPage stub, low value, dropped), `author` (a single inline
             `Person` object -- not a list like Guardian Nigeria, not a
             bare `{"@id": ...}` ref like Premium Times), `editor` (same
             shape as author, often the same person -- kept separately
             since upstream keeps it separate), `publisher` (an inline
             `Organization` object with `name` and a `logo` ImageObject --
             no `@id` resolution needed, unlike Guardian Nigeria), `image`
             (a list of `ImageObject`s, passed through raw).
             HTML entities (`&nbsp;` etc.) appear in `description` and
             `articleBody` text -- `html.unescape()` applied to every text
             field pulled from the JSON-LD for robustness. NOTE: an
             apostrophe rendered as a box/replacement glyph in one
             terminal during recon turned out to be a false alarm -- the
             underlying character is the correct U+2019 (RIGHT SINGLE
             QUOTATION MARK), confirmed via codepoint inspection; there is
             no real mojibake/encoding quirk on this site.
             A page that 200-OKs but is not an article (e.g.
             `/privacy-policy/`) carries ZERO `application/ld+json` blocks
             at all -- simpler to detect than Guardian Nigeria/Punch, which
             still emit a graph without a NewsArticle node on non-article
             pages. Reported as `_error: "not_article"`.
             A genuinely deleted/never-existed slug returns a REAL HTTP 404
             (confirmed on a deliberately-invented slug) -- no soft-404
             quirk observed.
  S2-rss   -- `/feed/` (WordPress core feed). Each `<item>` carries `title`,
             `link`, `dc:creator` (a REAL per-article byline, unlike
             punchng.com's constant generic "Punch Newspapers"), `pubDate`,
             REAL per-article `<category>` tags (section + tags, unlike
             Punch's always-empty category), a `guid`, and a teaser
             `description` (CDATA HTML: an `<img>` tag plus a truncated
             `<p>` ending in a WordPress "[&#8230;]" ellipsis marker, plus a
             trailing "Read More" link paragraph -- real feed content, kept
             as-is, `html.unescape()`d). No `<enclosure>` tag is present on
             any sampled item (unlike Punch), so no `enclosureUrl` field is
             emitted -- not fabricated as an always-null field.
"""

import html
import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


class ArticleNotFound(Exception):
    """The page 200-OK'd but is not an article (no ld+json NewsArticle node
    at all) -- e.g. a static page like /privacy-policy/. An expected
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


def _find_article_node(soup: BeautifulSoup) -> dict | None:
    """dailypost.ng emits a flat JSON array (not a Yoast @graph) per
    ld+json block -- usually one block, one item. Scan every block and
    every top-level item defensively in case that ever changes.
    """
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            node_type = item.get("@type")
            types = node_type if isinstance(node_type, list) else [node_type]
            if any(t in {"NewsArticle", "Article"} for t in types):
                return item
    return None


def _person_name(value) -> str | None:
    """`author`/`editor` are a single inline Person object on this site,
    but handled defensively as a list too in case of a future shape change.
    """
    if value is None:
        return None
    items = value if isinstance(value, list) else [value]
    names = [html.unescape(i["name"]) for i in items if isinstance(i, dict) and i.get("name")]
    return ", ".join(names) if names else None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article = _find_article_node(soup)
    if article is None:
        # Either no ld+json block at all (e.g. /privacy-policy/) or a block
        # with no NewsArticle-typed item -- both mean "not an article".
        raise ArticleNotFound(f"No NewsArticle ld+json node found for {url} -- not an article page.")

    article_body = _unescape(article.get("articleBody"))
    if not article_body:
        raise UnexpectedShape("articleBody missing/empty in ld+json -- page shape has likely changed.")

    publisher_node = article.get("publisher") if isinstance(article.get("publisher"), dict) else None
    publisher = html.unescape(publisher_node["name"]) if publisher_node and publisher_node.get("name") else None
    if publisher is None:
        og_site_name = soup.find("meta", attrs={"property": "og:site_name"})
        publisher = og_site_name.get("content") if og_site_name else None

    description = _unescape(article.get("description"))
    if not description:
        meta_desc_tag = soup.find("meta", attrs={"name": "description"})
        description = meta_desc_tag.get("content") if meta_desc_tag else None

    return {
        "_input": url,
        "_source": "S1-jsonld",
        "_scrapedAt": utc_now_iso(),
        "headline": _unescape(article.get("headline")),
        "description": description,
        "articleBody": article_body,
        "author": _person_name(article.get("author")),
        "editor": _person_name(article.get("editor")),
        "publisher": publisher,
        "articleSection": _unescape(article.get("articleSection")),
        "keywords": _unescape(article.get("keywords")),
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "thumbnailUrl": article.get("thumbnailUrl"),
        "image": article.get("image"),
        "wordCount": article.get("wordCount"),
        "timeRequired": article.get("timeRequired"),
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
