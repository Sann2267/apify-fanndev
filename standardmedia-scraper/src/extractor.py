"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- Most standardmedia.co.ke sections (national, opinion,
               crime-and-justice, politics, education, explainers,
               branding-voice, asia, xn-iraki, health, ...) emit a
               top-level (non-@graph) `NewsArticle` ld+json node that
               carries **`articleBody` with the FULL article text inline**
               -- no HTML scraping needed for these. Also present:
               `headline`, `articleSection` (list), `image` (list of URL
               strings), `datePublished`/`dateModified`, `author` (list of
               `Person` objects), `isAccessibleForFree` (bool) and a
               `hasPart` node naming a `.paywall` CSS selector (Piano-style
               paywall metadata) -- but see Paywall behavior below, it does
               not truncate the ld+json body.
               **Key quirk (double HTML-entity escaping):** `articleBody`
               is emitted DOUBLE html-entity-escaped on the wire, e.g. a
               literal `&nbsp;` in the source content is served as literal
               `&amp;nbsp;` inside the JSON string (confirmed on raw wire
               bytes, not a decoding artifact of this actor). A single
               `html.unescape()` only recovers `&nbsp;`; it takes TWO
               passes to recover the real `\xa0` character. The extractor
               therefore calls `html.unescape()` twice. This is idempotent
               for ordinary text (a literal "H&M" is unaffected by either
               pass, since there's no entity pattern to match), so it's
               safe to always apply.
               The JSON itself also contains raw, unescaped `\r\n` control
               characters inside string values (also confirmed on the
               wire) -- standard-library `json.loads` rejects this by
               default (`Invalid control character`); the extractor parses
               with `strict=False` to tolerate it.
  S2-html   -- The `evewoman` (lifestyle) section uses a DIFFERENT article
               template: its `NewsArticle` ld+json node has NO
               `articleBody` key at all (only `headline`/`description`/
               `image`/`author`/dates/`articleSection`/`publisher`), and
               uses `@context: "http://schema.org"` (note: `http`, not
               `https`, unlike the main template). Full text for this
               template comes from `div.story-body` (aliased by a
               `div.content-body` wrapper one level up) in the HTML,
               proper `<p class="paragraph-style">` tags this time (unlike
               ghanaweb's `<br>`-only legacy template) -- but interspersed
               with empty `<p></p>` spacer tags and inline ad `<div
               class="ad" id="div-gpt-ad-...">`/`<script>` blocks that must
               be stripped before joining paragraphs. Confirmed this
               fallback is genuinely needed (not just an unsampled edge
               case) by testing multiple evewoman URLs; every other
               section sampled (10+ articles across 6+ sections via the
               Google News sitemap) carried a populated `articleBody` in
               ld+json and used S1 instead.
  latest    -- S2-sitemap: Google News sitemap at
               `/sitemaps/googlenews.php` (see constants.py / client.py).
"""

import html
import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

ARTICLE_ID_RE = re.compile(r"/article/(\d+)/")
AD_SELECTORS = ["script", "style", "iframe", "ins", "div.ad", "div[id^='div-gpt-ad']"]


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_article_id(url: str) -> str | None:
    m = ARTICLE_ID_RE.search(url.split("?")[0])
    return m.group(1) if m else None


def _section_from_url(url: str) -> str | None:
    # https://www.standardmedia.co.ke/<section>/article/<id>/<slug> (or
    # https://www.standardmedia.co.ke/<section>/<subsection>/article/<id>/<slug>
    # on some templates, e.g. evewoman) -- take the first path segment.
    m = re.match(r"https?://[^/]+/([^/]+)/", url)
    return m.group(1) if m else None


def _find_ld_json_node(soup: BeautifulSoup, type_name: str) -> dict | None:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw, strict=False)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        graph = data.get("@graph")
        nodes = graph if isinstance(graph, list) else [data]
        for node in nodes:
            if isinstance(node, dict) and node.get("@type") == type_name:
                return node
    return None


def _clean_body_text(raw: str) -> str:
    # See module docstring -- double html-entity-escaped on the wire.
    return html.unescape(html.unescape(raw)).strip()


def _extract_html_body(soup: BeautifulSoup) -> str:
    container = soup.select_one("div.story-body") or soup.select_one("div.content-body")
    if container is None:
        raise UnexpectedShape("No div.story-body / div.content-body element found -- page shape has likely changed.")

    for sel in AD_SELECTORS:
        for el in container.select(sel):
            el.decompose()

    paragraphs = []
    for p in container.find_all("p"):
        text = p.get_text(strip=True)
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    news_article = _find_ld_json_node(soup, "NewsArticle")
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json node found -- page shape has likely changed.")

    raw_body = news_article.get("articleBody")
    if raw_body:
        source = "S1-jsonld"
        article_body = _clean_body_text(raw_body)
    else:
        source = "S2-html"
        article_body = _extract_html_body(soup)

    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text from both S1 and S2 -- page shape has likely changed.")

    article_section = news_article.get("articleSection")
    category = article_section[0] if isinstance(article_section, list) and article_section else article_section

    return {
        "_input": url,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "articleId": _extract_article_id(url),
        "headline": news_article.get("headline"),
        "description": news_article.get("description"),
        "articleBody": article_body,
        "articleSection": article_section,
        "category": category,
        "author": news_article.get("author"),
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "image": news_article.get("image"),
        "isAccessibleForFree": news_article.get("isAccessibleForFree"),
        "canonicalUrl": news_article.get("mainEntityOfPage") or news_article.get("@id"),
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def extract_sitemap_items(xml_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    url_nodes = soup.find_all("url")
    if not url_nodes:
        raise UnexpectedShape("No <url> elements found in Google News sitemap -- feed shape has likely changed.")
    results = []
    for url_node in url_nodes:
        loc = url_node.find("loc")
        title = url_node.find("news:title")
        pub_date = url_node.find("news:publication_date")
        language = url_node.find("news:language")
        lastmod = url_node.find("lastmod")
        image_loc = url_node.find("image:loc")
        image_caption = url_node.find("image:caption")
        link = loc.text.strip() if loc and loc.text else None
        results.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "articleId": _extract_article_id(link) if link else None,
                "title": title.text.strip() if title and title.text else None,
                "link": link,
                "section": _section_from_url(link) if link else None,
                "publicationDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "language": language.text.strip() if language and language.text else None,
                "lastmod": lastmod.text.strip() if lastmod and lastmod.text else None,
                "imageUrl": image_loc.text.strip() if image_loc and image_loc.text else None,
                "imageCaption": image_caption.text.strip() if image_caption and image_caption.text else None,
            }
        )
    return results
