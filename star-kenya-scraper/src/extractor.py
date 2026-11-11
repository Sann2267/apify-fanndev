"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-flight+html -- the-star.co.ke is a Next.js App Router site. There is NO
               `<script type="application/ld+json">` tag and NO
               `__NEXT_DATA__` blob anywhere in the SSR HTML -- both classic
               anchors this portfolio prefers are absent. Instead, the
               `NewsArticle` JSON-LD object is embedded inside a React
               Server Components "flight" payload: one of several
               `<script>self.__next_f.push([1,"..."])</script>` tags, where
               the second array element is a JSON-encoded STRING (i.e. the
               flight protocol text itself is escaped one level deeper than
               ordinary inline JSON). `_iter_next_f_strings()` balanced-
               bracket-extracts each `push([...])` call, `json.loads()`s the
               2-element array (which un-escapes the string in one step),
               then `_find_json_ld()` balanced-brace-extracts the `"jsonLd":
               {...}` object out of the now-plain-JSON flight text and
               `json.loads()`s it directly -- no manual unescaping needed at
               either stage, see skills/balanced-brace-json.md. The jsonLd
               node carries `headline`, `datePublished`, `author` (single
               Person object), `image` (list of ImageObject), `publisher`,
               and on premium/paywalled articles ONLY, `isAccessibleForFree:
               false` + a `hasPart` node naming a `.premium-content` CSS
               selector -- but see Paywall behavior below, it never carries
               `articleBody`.
  S1-flight+html body -- the full article text is NOT in the flight jsonLd at
               all (no `articleBody` key exists on this CMS's NewsArticle
               node, confirmed on every sample). It comes from the rendered
               HTML instead: one or more `<div class="story-content">`
               elements. Non-premium articles have exactly one (image +
               body together); premium/paywalled articles have TWO -- an
               outer one holding just the lead image (shown free), and a
               second one nested inside `<div class="premium-gate">
               <div class="premium-content">` holding the real paragraphs
               (marked `aria-hidden="true"` for the CSS-driven visual gate,
               but the full text is still server-rendered into the HTML
               regardless of `isAccessibleForFree` -- see Paywall behavior).
               Taking the LAST `div.story-content` on the page handles both
               cases uniformly: it's the only one when there's one, and the
               full-text one when there are two.
  latest    -- S2-sitemap: `/articles/sitemap/1.xml` (one of 50 numbered
               sitemaps listed in `/sitemap_index.xml`), a plain XML sitemap
               (`loc`/`lastmod`/`changefreq` only -- no `news:` namespace,
               no title). Confirmed same-day freshness. Since entries are
               NOT reliably lastmod-sorted within the file and there's no
               title field, `extract_sitemap_items()` sorts by `lastmod`
               descending and derives a readable title from the URL slug
               (date prefix stripped, hyphens -> spaces, title-cased) --
               cosmetic only, not a substitute for the real `headline` you
               get from `article` mode.

Not-found: two distinct shapes, see main.py/test_local.py:
  - Malformed URL (date segment doesn't match `YYYY-MM-DD-`) -> real HTTP 404.
  - Well-formed but nonexistent slug -> HTTP 200, but the page silently falls
    back to a generic homepage-shell template: no flight jsonLd, no
    `story-content` div, and `<title>` is the bare site name "The Star"
    (a real article's `<title>` is always its headline text, confirmed on
    every sample -- no site-name suffix). extract_article() raises
    UnexpectedShape only when the jsonLd is missing AND the title is NOT
    this exact soft-404 marker, so genuine template drift still fails loud.
"""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

SOFT_404_TITLE = "The Star"
# https://www.the-star.co.ke/<section>[/<subsection>...]/YYYY-MM-DD-slug
DATE_SLUG_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)$")


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_balanced(text: str, start: int, open_ch: str, close_ch: str) -> str | None:
    """Balanced open/close-char walker that tracks JSON string quoting so
    braces/brackets inside string values don't throw off the depth count.
    See skills/balanced-brace-json.md."""
    if start >= len(text) or text[start] != open_ch:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    return None  # truncated / unbalanced


def _iter_next_f_strings(html_text: str):
    """Yield the (already one-level-unescaped) string payload of every
    `self.__next_f.push([1,"..."])` flight chunk in the page."""
    for m in re.finditer(r"self\.__next_f\.push\(", html_text):
        start = html_text.find("[", m.end())
        if start == -1:
            continue
        blob = _extract_balanced(html_text, start, "[", "]")
        if blob is None:
            continue
        try:
            arr = json.loads(blob)
        except json.JSONDecodeError:
            continue
        if isinstance(arr, list) and len(arr) >= 2 and isinstance(arr[1], str):
            yield arr[1]


def _find_json_ld(html_text: str) -> dict | None:
    for chunk in _iter_next_f_strings(html_text):
        idx = chunk.find('"jsonLd":')
        while idx != -1:
            brace_start = chunk.find("{", idx)
            if brace_start == -1:
                break
            blob = _extract_balanced(chunk, brace_start, "{", "}")
            if blob is not None:
                try:
                    data = json.loads(blob)
                except json.JSONDecodeError:
                    data = None
                if isinstance(data, dict) and data.get("@type") == "NewsArticle":
                    return data
            idx = chunk.find('"jsonLd":', idx + 1)
    return None


def _extract_html_body(soup: BeautifulSoup) -> str:
    containers = soup.select("div.story-content")
    if not containers:
        raise UnexpectedShape("No div.story-content element found -- page shape has likely changed.")
    # Premium/paywalled articles render TWO: the first holds only the lead
    # image (shown free), the second (nested in div.premium-content) holds
    # the full body. Non-premium articles render exactly one. The LAST one
    # is always the full-text container in both cases.
    container = containers[-1]
    paragraphs = []
    for p in container.find_all("p"):
        text = p.get_text(" ", strip=True)
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _path_segments(url: str) -> list[str]:
    m = re.match(r"https?://[^/]+/(.+?)/?(?:\?.*)?$", url)
    return m.group(1).split("/") if m else []


def _section_and_slug(url: str) -> tuple[str | None, str | None, str | None, str | None]:
    """Returns (section, subsection, date, slug) from
    /<section>[/<subsection>]/YYYY-MM-DD-slug."""
    segments = _path_segments(url)
    if not segments:
        return None, None, None, None
    last = segments[-1]
    date_match = DATE_SLUG_RE.match(last)
    date, slug = (date_match.group(1), date_match.group(2)) if date_match else (None, last)
    section = segments[0] if segments else None
    subsection = "/".join(segments[1:-1]) or None
    return section, subsection, date, slug


def _title_from_slug(slug: str | None) -> str | None:
    if not slug:
        return None
    return slug.replace("-", " ").strip().title() or None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    news_article = _find_json_ld(html_text)
    if news_article is None:
        title_tag = soup.find("title")
        title_text = title_tag.get_text(strip=True) if title_tag else None
        if title_text == SOFT_404_TITLE:
            return extract_error(url, "not_found", "generic homepage-shell template, no flight jsonLd")
        raise UnexpectedShape("No NewsArticle flight jsonLd found -- page shape has likely changed.")

    # NOTE: an empty string is a legitimate result here, not just an
    # extraction failure -- some content types on this site (editorial
    # cartoons under /opinion/cartoon/, and likely the /in-pictures photo-
    # gallery section) render a div.story-content that holds only an image,
    # with zero <p> text. _extract_html_body() already raises UnexpectedShape
    # if the container itself is missing entirely (real template drift); an
    # empty-but-present container is passed through as articleBody: "" so a
    # genuinely bodyless article doesn't crash the whole run.
    article_body = _extract_html_body(soup)

    section, subsection, date, slug = _section_and_slug(url)
    has_part = news_article.get("hasPart") or {}

    return {
        "_input": url,
        "_source": "S1-flight+html",
        "_scrapedAt": utc_now_iso(),
        "headline": news_article.get("headline"),
        "description": news_article.get("description"),
        "articleBody": article_body,
        "section": section,
        "subsection": subsection,
        "slug": slug,
        "author": news_article.get("author"),
        "datePublished": news_article.get("datePublished"),
        "image": news_article.get("image"),
        "isAccessibleForFree": news_article.get("isAccessibleForFree"),
        "paywallSelector": has_part.get("cssSelector") if isinstance(has_part, dict) else None,
        "canonicalUrl": news_article.get("mainEntityOfPage"),
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
        raise UnexpectedShape("No <url> elements found in article sitemap -- feed shape has likely changed.")

    results = []
    for url_node in url_nodes:
        loc = url_node.find("loc")
        lastmod = url_node.find("lastmod")
        link = loc.text.strip() if loc and loc.text else None
        if not link:
            continue
        section, subsection, date, slug = _section_and_slug(link)
        results.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": _title_from_slug(slug),
                "link": link,
                "section": section,
                "subsection": subsection,
                "date": date,
                "lastmod": lastmod.text.strip() if lastmod and lastmod.text else None,
            }
        )

    # Entries aren't reliably lastmod-sorted within the file -- sort
    # descending so callers get the freshest items first regardless.
    results.sort(key=lambda r: r["lastmod"] or "", reverse=True)
    return results
