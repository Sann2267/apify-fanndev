"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- english.aawsat.com (Asharq Al-Awsat's English edition,
             Drupal-based, same CMS family as gulfnews/arabnews/
             omanobserver in this portfolio) emits exactly one
             `<script type="application/ld+json">` block per article,
             wrapped in a `@graph` array with a single node. The node's
             `@type` varies by content bundle -- confirmed `NewsArticle`
             for regular news/business/sport pieces and
             `OpinionNewsArticle` for opinion columns (both are valid
             schema.org NewsArticle subtypes) -- so the extractor matches
             any node whose `@type` string *contains* "NewsArticle" rather
             than an exact match, to tolerate other subtypes
             (`ReportageNewsArticle`, `AnalysisNewsArticle`, etc.) that
             weren't sampled but follow the same CMS convention. That node
             carries `headline`, `description`, `datePublished`,
             `dateModified`, `image` (`ImageObject`), `author` (a single
             `Person` -- generic "Asharq Al Awsat" for staff/wire news,
             a real named columnist e.g. "Nabil Amr" for opinion pieces),
             and `publisher` (an `Organization` whose `name` is always the
             Arabic "الشرق الأوسط", NOT an English "Asharq Al-Awsat" string,
             even on the English-edition page -- passed through as-is,
             raw-passthrough convention, not translated/renamed) -- but
             **no `articleBody`**. Full text instead comes from HTML: the
             page has exactly one element with `id="article_node_id"` (a
             `div.entry-content` node carrying `data-nid`/`data-url`/
             `data-bundle` attributes) and the extractor collects the text
             of every `<p>` tag found anywhere inside it (recursive, not
             just direct children -- news-bundle pages nest `<p>` directly
             under `#article_node_id` while opinion-bundle pages nest them
             one level deeper inside a `div.field--name-body` wrapper, so a
             direct-children-only selector would miss opinion body text).
             Ad-slot `<div class="block-wrapper">` siblings interleaved
             between paragraphs carry no `<p>` text of their own and are
             skipped automatically since empty-text elements are filtered
             out. `category` is not present in the ld+json at all -- pulled
             instead from `div.entry-category a` inside the closest
             `div.entry-article` ancestor of the body element (present on
             every sample, both bundles). No `isAccessibleForFree` or other
             paywall marker was found in any of 2 sampled articles (one
             hard-news/business piece, one opinion column) -- appears fully
             open-access, consistent with the rest of the portfolio's
             Middle East English-language outlets.
  S2-html-listing -- no usable English-language feed exists. robots.txt on
             both aawsat.com and english.aawsat.com advertises
             `Sitemap: https://aawsat.com/googlenews.xml` and
             `/sitemap.xml`, but both resolve on the root Arabic domain and
             carry Arabic-only titles/URLs (`news:language` says `en` on
             `english.aawsat.com/googlenews.xml` but the `<loc>` is empty
             and titles are still Arabic -- a broken/mismapped feed on that
             subdomain, not a real English feed). `/feed` on
             english.aawsat.com returns HTTP 200 but is the homepage HTML,
             not an RSS document. Instead, the homepage
             (`https://english.aawsat.com/`) is scraped for
             `<div role="article" typeof="schema:Article">` blocks (RDFa
             markup Drupal emits for every teased article on the page) --
             each carries the canonical URL in its `about` attribute, the
             numeric node ID in `data-nid`, and a clean, already-decoded
             headline in a nested `<span property="schema:name"
             content="...">` tag (no gluing-headline-to-teaser issue, since
             this span carries ONLY the headline, unlike anchor
             `.get_text()` which would pick up teaser paragraphs from the
             same block). One homepage fetch yields ~44 unique articles
             after dedup by node ID (57 raw blocks incl. duplicate
             placements of the same story in multiple homepage widgets).
             Sorted newest-first by numeric node ID descending, since
             homepage module/widget placement does not reliably match
             recency (verified: IDs are not monotonic in DOM order).
"""

import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iter_ld_nodes(soup: BeautifulSoup):
    """Yield every dict node from every ld+json block, unwrapping @graph."""
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and isinstance(data.get("@graph"), list):
            for node in data["@graph"]:
                if isinstance(node, dict):
                    yield node
        elif isinstance(data, dict):
            yield data


def _find_news_article(soup: BeautifulSoup) -> dict | None:
    for node in _iter_ld_nodes(soup):
        type_val = node.get("@type")
        if isinstance(type_val, str) and "NewsArticle" in type_val:
            return node
    return None


def _org_name(node):
    if isinstance(node, dict):
        return node.get("name")
    return node


def _extract_body(soup: BeautifulSoup) -> str:
    div = soup.find(id="article_node_id")
    if div is None:
        raise UnexpectedShape("No #article_node_id element found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in div.find_all("p") if p.get_text(strip=True)]
    return "\n\n".join(paragraphs)


def _extract_category(soup: BeautifulSoup, body_div) -> str | None:
    wrapper = body_div.find_parent("div", class_="entry-article") if body_div else None
    if wrapper is None:
        return None
    tag = wrapper.select_one(".entry-category a")
    return tag.get_text(strip=True) if tag else None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article = _find_news_article(soup)
    if article is None:
        raise UnexpectedShape("No NewsArticle-type ld+json block found -- page shape has likely changed.")

    body_div = soup.find(id="article_node_id")
    article_body = _extract_body(soup)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    image = article.get("image")
    image_url = image.get("url") if isinstance(image, dict) else (image if isinstance(image, str) else None)

    return {
        "_input": url,
        "_source": "S1-jsonld+html",
        "_scrapedAt": utc_now_iso(),
        "headline": article.get("headline"),
        "description": article.get("description"),
        "about": article.get("about"),
        "articleBody": article_body,
        "articleType": article.get("@type"),
        "category": _extract_category(soup, body_div),
        "author": _org_name(article.get("author")),
        "publisher": _org_name(article.get("publisher")),
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


def extract_latest_items(html_text: str) -> list[dict]:
    soup = BeautifulSoup(html_text, "lxml")

    blocks = soup.find_all("div", attrs={"role": "article", "typeof": "schema:Article"})
    if not blocks:
        raise UnexpectedShape("No div[role=article][typeof=schema:Article] blocks found -- homepage shape has likely changed.")

    seen: dict[str, tuple[str, str]] = {}
    for block in blocks:
        nid = block.get("data-nid")
        about = block.get("about")
        if not nid or not about or nid in seen:
            continue
        span = block.find("span", attrs={"property": "schema:name"})
        title = span.get("content").strip() if span and span.get("content") else None
        seen[nid] = (title, about)

    ordered_ids = sorted(seen.keys(), key=lambda i: int(i), reverse=True)

    items = []
    for nid in ordered_ids:
        title, link = seen[nid]
        items.append(
            {
                "_input": "latest",
                "_source": "S2-html-listing",
                "_scrapedAt": utc_now_iso(),
                "title": title,
                "link": link,
                "articleId": int(nid),
            }
        )
    return items
