"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- arabnews.com (Drupal-based) emits a single `NewsArticle`
               ld+json block per article. It still carries the metadata --
               headline, author, dates, section, image, keywords -- and is
               the primary source for all of them. `author` is always a
               single `Person` dict (often a wire service like
               "Reuters"/"AP"/"SPA" rather than a named byline). No
               `isAccessibleForFree` or other paywall marker was found in
               any sampled article; the site appears fully open-access.

               **It no longer carries `articleBody`.** Until some time
               before 2026-09-23 the block included the body as real,
               un-escaped HTML markup. Arab News has since dropped the
               field: re-measured 2026-09-23 across six live articles from
               the news sitemap, `articleBody` was absent from the ld+json
               on 6 of 6 while the block itself was intact on 6 of 6.
               `description` came back empty too. This is a CMS change, not
               a per-article quirk, and it is what made a cloud run fail
               with `articleBody missing from NewsArticle node`.

  S1b-html   -- the body fallback, used whenever `articleBody` is missing
               from the ld+json (which is now always). The article text
               lives in the page at `.article-body`, one node per article,
               8-26 `<p>` tags and 1.5-4 KB of text across the same six
               samples. Records built this way are tagged
               `_source: "S1-jsonld+html-body"` so a consumer can tell which
               articles needed the fallback without re-fetching. If Arab
               News restores `articleBody`, the ld+json path resumes on its
               own and the tag goes back to `S1-jsonld`.
  S2-sitemap -- Google News sitemap (`/googlenews.xml`, advertised via
               `Sitemap:` in robots.txt) for `latest` mode. Minimal shape:
               just `news:title` + `news:publication_date` per `<url>`, no
               image or keyword blocks (unlike gulfnews-scraper's sitemap).
"""

import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_news_article(soup: BeautifulSoup) -> dict | None:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "NewsArticle":
            return data
    return None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article = _find_news_article(soup)
    if article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    raw_body = article.get("articleBody")
    source = "S1-jsonld"
    if raw_body:
        # When present it is real (un-escaped) HTML, not plain text.
        article_body = _paragraphs(BeautifulSoup(raw_body, "lxml"))
    else:
        # Arab News dropped articleBody from the ld+json; the text is only in
        # the page now. Raising here would reject every article on the site.
        article_body = _body_from_html(soup)
        source = "S1-jsonld+html-body"
    if not article_body:
        raise UnexpectedShape(
            "No article text found: the ld+json carried no articleBody and "
            f"none of the page selectors {BODY_SELECTORS} matched any text. "
            "Both the JSON and the HTML shape have changed."
        )

    author_name = _first_name(article.get("author"))
    image_url = _first_url(article.get("image"))

    return {
        "_input": url,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "headline": article.get("headline"),
        "articleBody": article_body,
        "articleSection": article.get("articleSection"),
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "author": author_name,
        "image": image_url,
    }


# Where the article text lives now that the ld+json no longer carries it.
# Tried in order; `.article-body` matched exactly 1 node on 6 of 6 live
# articles on 2026-09-23. The rest are Drupal defaults, kept as cheap
# insurance against the theme being renamed again.
BODY_SELECTORS = (
    ".article-body",
    "div.field--name-body",
    "div[property='content:encoded']",
    "#article-body",
)


def _first_name(value) -> str | None:
    """The byline, however schema.org happens to be wrapping it today.

    Measured 2026-09-23: `author` is now a LIST of Person/Organization dicts
    (`[{"@type": "Organization", "name": "Reuters"}]`), where it used to be a
    bare dict. The old code asked a list for `.get("name")`, got None, and
    published a null byline on every article without ever failing -- the exact
    silent-corruption shape this portfolio's error-handling convention exists
    to prevent. All three shapes are accepted now.
    """
    if isinstance(value, list):
        value = next((v for v in value if v), None)
    if isinstance(value, dict):
        name = value.get("name")
        return str(name) if name else None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _first_url(value) -> str | None:
    """The lead image, likewise.

    `image` is now a LIST of plain URL strings; it used to be an ImageObject
    dict with a `url` key. Same silent-null failure as `author` above.
    """
    if isinstance(value, list):
        value = next((v for v in value if v), None)
    if isinstance(value, dict):
        url = value.get("url")
        return str(url) if url else None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _paragraphs(node) -> str:
    """Join a node's <p> text, falling back to its flat text."""
    paragraphs = [
        p.get_text(" ", strip=True)
        for p in node.find_all("p")
        if p.get_text(strip=True)
    ]
    if paragraphs:
        return '\n\n'.join(paragraphs)
    return node.get_text(" ", strip=True)


def _body_from_html(soup) -> str:
    """The article text from the page itself, for the post-2026-09 layout."""
    for selector in BODY_SELECTORS:
        for node in soup.select(selector):
            text = _paragraphs(node)
            if text:
                return text
    return ""


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
        items.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": loc.text.strip() if loc and loc.text else None,
                "publicationDate": pub_date.text.strip() if pub_date and pub_date.text else None,
            }
        )
    return items
