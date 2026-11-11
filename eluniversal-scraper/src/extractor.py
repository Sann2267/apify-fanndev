"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- eluniversal.com.mx runs on Arc Publishing (same CMS
               family as gulfnews-scraper/thenational-scraper) and emits
               `BreadcrumbList` + `NewsArticle` ld+json blocks with rich
               metadata (`headline`, `description`, `author`, dates,
               `isAccessibleForFree`, `keywords`, `image`, `dateline`) but
               **no `articleBody` field**. Body text is scraped from HTML,
               scoped to `<div class="content-story">` (found by walking
               up from a known body paragraph during recon -- the wider
               `<article>` tag on this CMS instance contained ZERO `<p>`
               tags, all real content lives in this narrower div). Two
               kinds of boilerplate paragraphs are filtered by exact/
               prefix match: literal `"[Publicidad]"` ad-slot placeholders
               (scattered mid-article, several per story) and a WhatsApp-
               channel promo CTA (`"Únete a nuestro canal ¡EL UNIVERSAL ya
               está en Whatsapp!..."`) that appears once near the end of
               every article. Inline `"Lee también <related headline>"`
               cross-links are LEFT IN as real body text (genuine editorial
               content, not UI chrome) -- same treatment as the dek
               paragraph in `independent-scraper`.
               `keywords` arrives as a comma-separated string, split into a
               list to match the shape used elsewhere in this portfolio.
  S2-sitemap  -- Arc Publishing outbound rolling news sitemap
               (`/arc/outboundfeeds/news/?outputType=xml`, advertised in
               robots.txt). `news:title` and `news:keywords` are wrapped in
               `<![CDATA[...]]>` blocks -- passed through as-is since no
               escaped entities were found inside them in samples (unlike
               independent-scraper/koreatimes-scraper, where CDATA content
               happened to contain literal `&amp;`/`&apos;`) -- `image:loc`
               and `image:caption` are NOT CDATA-wrapped here, so their
               `&amp;` query-string separators are correctly XML-decoded
               by the parser already, no extra unescape needed.
"""

import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup

AD_PLACEHOLDER = "[Publicidad]"
WHATSAPP_CTA_PREFIX = "Únete a nuestro canal"


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

    container = soup.find("div", class_="content-story")
    if container is None:
        raise UnexpectedShape("No div.content-story element found -- page shape has likely changed.")
    paragraphs = []
    for p in container.find_all("p"):
        text = p.get_text(" ", strip=True)
        if not text or text == AD_PLACEHOLDER or text.startswith(WHATSAPP_CTA_PREFIX):
            continue
        paragraphs.append(text)
    article_body = "\n\n".join(paragraphs)
    if not article_body:
        raise UnexpectedShape("No body paragraphs found in div.content-story -- page shape has likely changed.")

    author = article.get("author")
    if isinstance(author, list):
        author_name = ", ".join(a.get("name") for a in author if isinstance(a, dict) and a.get("name"))
    elif isinstance(author, dict):
        author_name = author.get("name")
    else:
        author_name = None

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
        keywords = url_node.find("news:keywords")
        image = url_node.find("image:loc")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": loc.text.strip() if loc and loc.text else None,
                "publicationDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "keywords": [k.strip() for k in keywords.text.split(",")] if keywords and keywords.text else [],
                "imageUrl": image.text.strip() if image and image.text else None,
            }
        )
    return items
