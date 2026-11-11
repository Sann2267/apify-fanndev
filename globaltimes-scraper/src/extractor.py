"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-html    -- globaltimes.cn emits **no ld+json at all** and almost no
               useful `<meta>` tags (only `og:image`) -- this is the only
               actor in the portfolio so far with zero structured-data
               markup. All fields are scraped from plain HTML:
                 - `headline` from `<title>`, with the `" - Global Times"`
                   site-name suffix stripped.
                 - `author`/`datePublished` from `<span class="byline">`
                   (e.g. `"By Xinhua"` or `"By Zhang Weilan and Qi Xijia"`
                   -- `"By "` prefix stripped) and `<span class="pub_time">`
                   (e.g. `"Published: Aug 23, 2026 09:59 PM"` -- passed
                   through as raw text, NOT parsed into ISO-8601, since the
                   portfolio convention is raw passthrough and this format
                   is ambiguous to parse reliably without a hardcoded
                   locale assumption).
                 - `articleBody` from `<div class="article_right">` --
                   this legacy CMS does **not** wrap paragraphs in `<p>`
                   tags at all; body text is one long run of text nodes
                   separated by `<br>` tags. The extractor replaces every
                   `<br>` with a newline, then re-groups lines into
                   paragraphs on blank-line boundaries (2+ consecutive
                   newlines = paragraph break). Before doing this, every
                   `<p class="picture">` (image caption) is `.decompose()`d
                   first -- these captions duplicate the article's opening
                   sentence almost verbatim (confirmed across 3 samples)
                   plus a trailing photo credit, and would otherwise appear
                   as a spurious near-duplicate first paragraph.
  S2-sitemap -- Google News sitemap (`/sitemap.xml`, advertised in
               robots.txt). Standard shape: `news:title`,
               `news:publication_date` (proper ISO-8601, unlike the
               article page's raw `pub_time` string), `news:keywords`
               (comma-separated, with a trailing empty element in one
               sample -- `"cooperation,global,italy,dialogue,china,"` --
               filtered out by the existing non-empty check after
               stripping).
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

TITLE_SUFFIX_RE = re.compile(r"\s*-\s*Global Times\s*$")


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    body_el = soup.find(class_="article_right")
    if body_el is None:
        raise UnexpectedShape("No div.article_right element found -- page shape has likely changed.")

    for caption in body_el.find_all("p", class_="picture"):
        caption.decompose()
    for br in body_el.find_all("br"):
        br.replace_with("\n")

    lines = [line.strip() for line in body_el.get_text().split("\n")]
    paragraphs, current = [], []
    for line in lines:
        if line:
            current.append(line)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    article_body = "\n\n".join(paragraphs)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    title_tag = soup.find("title")
    headline = TITLE_SUFFIX_RE.sub("", title_tag.text.strip()) if title_tag and title_tag.text else None

    byline = soup.find(class_="byline")
    author = byline.get_text(strip=True) if byline else None
    if author and author.startswith("By "):
        author = author[3:]

    pub_time = soup.find(class_="pub_time")
    published_raw = pub_time.get_text(strip=True) if pub_time else None

    return {
        "_input": url,
        "_source": "S1-html",
        "_scrapedAt": utc_now_iso(),
        "headline": headline,
        "articleBody": article_body,
        "author": author,
        "publishedRaw": published_raw,
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
    items = []
    for url_node in soup.find_all("url"):
        loc = url_node.find("loc")
        title = url_node.find("news:title")
        pub_date = url_node.find("news:publication_date")
        keywords = url_node.find("news:keywords")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": loc.text.strip() if loc and loc.text else None,
                "publicationDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "keywords": [k.strip() for k in keywords.text.split(",") if k.strip()]
                if keywords and keywords.text
                else [],
            }
        )
    return items
