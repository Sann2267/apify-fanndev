"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- kyivindependent.com (Ghost CMS backend, Next.js
               frontend) emits a `NewsArticle` ld+json block with rich
               metadata (headline, description, author, dates,
               isAccessibleForFree, keywords, image) but **no
               `articleBody` field**. Body text is scraped from HTML:
               every `<p>` tag inside the page's `<article>` element --
               unlike independent-scraper, no UI boilerplate (login
               prompts, newsletter CTAs, comment prompts) was found mixed
               into the `<article>` container in any of the 2 sampled
               articles (7 and 21 real paragraphs respectively, first and
               last both genuine body text) -- so no prefix-filtering is
               applied here. `author` is a single `Person` dict with a
               long `description` bio field (not used -- only `name` is
               extracted). `keywords` is a **comma-separated string**, not
               a list -- split on `, ` to normalize.
  S2-sitemap  -- Google News sitemap (`/news-sitemap.xml`, advertised in
               robots.txt). Standard shape: `news:title`,
               `news:publication_date`, `lastmod`, one `image:image` block
               per entry.
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
        candidates = data if isinstance(data, list) else [data]
        for node in candidates:
            if isinstance(node, dict) and node.get("@type") == "NewsArticle":
                return node
    return None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    article = _find_news_article(soup)
    if article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    art_tag = soup.find("article")
    if art_tag is None:
        raise UnexpectedShape("No <article> element found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in art_tag.find_all("p") if p.get_text(strip=True)]
    article_body = "\n\n".join(paragraphs)
    if not article_body:
        raise UnexpectedShape("No body paragraphs found in <article> -- page shape has likely changed.")

    author = article.get("author")
    author_name = author.get("name") if isinstance(author, dict) else None

    keywords = article.get("keywords")
    keywords_list = [k.strip() for k in keywords.split(",")] if isinstance(keywords, str) else keywords

    image = article.get("image")
    image_url = image.get("url") if isinstance(image, dict) else (image if isinstance(image, str) else None)

    return {
        "_input": url,
        "_source": "S1-jsonld+html",
        "_scrapedAt": utc_now_iso(),
        "headline": article.get("headline"),
        "description": article.get("description"),
        "articleBody": article_body,
        "articleSection": article.get("articleSection"),
        "datePublished": article.get("datePublished"),
        "dateModified": article.get("dateModified"),
        "author": author_name,
        "isAccessibleForFree": article.get("isAccessibleForFree"),
        "keywords": keywords_list,
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


def extract_sitemap_items(xml_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    items = []
    for url_node in soup.find_all("url"):
        loc = url_node.find("loc")
        title = url_node.find("news:title")
        pub_date = url_node.find("news:publication_date")
        image = url_node.find("image:loc")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": loc.text.strip() if loc and loc.text else None,
                "publicationDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "imageUrl": image.text.strip() if image and image.text else None,
            }
        )
    return items
