"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- mg.co.za's `NewsArticle` ld+json block carries rich
               metadata (`headline`, `description`, `author` as a list,
               `keywords`, `image` as a list, `wordCount`, dates) but **no
               `articleBody` field**. Body text is scraped from HTML:
               every `<p>` tag inside the page's `<article>` element --
               unlike `independent-scraper`/`eluniversal-scraper`, **no UI
               boilerplate, ads, or promo CTAs were found mixed into the
               `<article>` container** in either of the 2 sampled articles
               (35 and 25 real paragraphs respectively) -- a plain
               `find_all("p")` join is sufficient, no filtering needed.
               `keywords` arrives as a comma-separated string, split into a
               list. `author`/`image` are both lists -- the first `image`
               entry's `url` is used as the lead image.
  S2-rss      -- site-wide RSS feed at `/rss/` (discovered by path probing
               -- NOT advertised in `robots.txt`, which only lists
               `sitemap.xml`; the sitemap tree turned out to be
               title-less, listing only `loc`+`lastmod` per article with
               no `news:news` metadata block, so RSS was used instead for
               a richer `latest` payload). Standard shape: `title`,
               `link`, `guid`, `pubDate`, `description` (a short teaser,
               genuinely different text from the ld+json `description` on
               the article page itself), plus an `<enclosure>` tag whose
               `url` attribute is the lead image (its `type` attribute is
               a CMS bug -- duplicates the image URL instead of a MIME
               type -- so only `url` is used, `type`/`length` are
               ignored).
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

    art_tag = soup.find("article")
    if art_tag is None:
        raise UnexpectedShape("No <article> element found -- page shape has likely changed.")
    paragraphs = [p.get_text(" ", strip=True) for p in art_tag.find_all("p") if p.get_text(strip=True)]
    article_body = "\n\n".join(paragraphs)
    if not article_body:
        raise UnexpectedShape("No body paragraphs found in <article> -- page shape has likely changed.")

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
    if isinstance(image, list) and image:
        first = image[0]
        image_url = first.get("url") if isinstance(first, dict) else first
    elif isinstance(image, dict):
        image_url = image.get("url")
    else:
        image_url = None

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
        "keywords": keywords_list,
        "wordCount": article.get("wordCount"),
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


def extract_rss_items(xml_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(xml_bytes, "xml")
    items = []
    for item in soup.find_all("item"):
        title = item.find("title")
        link = item.find("link")
        guid = item.find("guid")
        pub_date = item.find("pubDate")
        description = item.find("description")
        enclosure = item.find("enclosure")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "description": description.text.strip() if description and description.text else None,
                # enclosure's `type` attribute is a CMS bug (duplicates the
                # image URL instead of a MIME type) -- only `url` is used.
                "imageUrl": enclosure.get("url") if enclosure else None,
            }
        )
    return items
