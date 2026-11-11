"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld+html -- clarin.com emits 5 ld+json blocks per article page
               (`BreadcrumbList`, `Organization`, `NewsMediaOrganization`,
               `NewsArticle`, `ItemList`) -- the extractor scans all
               `<script type="application/ld+json">` tags and picks the
               one whose `@type` is (or contains) `"NewsArticle"` -- note
               `@type` arrives as a **list** (`["NewsArticle"]`), not a
               bare string like tass.com/eluniversal.com.mx, so the match
               has to handle both shapes. The block carries `headline`,
               `description`, `datePublished`, `dateModified`, `author`
               (a `Person` list for bylined opinion pieces, a single
               `Organization` dict for wire-style news -- and the author
               node uses a bare `"type"` key, not `"@type"`, unlike every
               other node on the page), `publisher`, `keywords` (comma-
               separated string), `image` (list of `ImageObject`),
               `articleSection`, and **`isAccessibleForFree`** (a genuine
               paywall flag -- see below) plus an `articleBody` field --
               but that ld+json `articleBody` is NOT used: recon found it
               has commas stripped throughout (e.g. "1,8%" is corrupted to
               "18%", changing the actual number), so it is unsafe for a
               numbers-heavy news site. Full text is instead scraped from
               HTML `#cuerpo` (a `div id="cuerpo"` nested inside
               `article#storyBody`) -- NOT the `.paywall_content` class
               that the ld+json `hasPart.cssSelector` points to, which
               turned out to be a red herring: that class is applied to
               the whole `<body>` tag site-wide (boilerplate schema
               markup, not a real content container) and selecting it
               would sweep in nav/footer/every `<p>` on the page. `#cuerpo`
               preserves punctuation correctly and was confirmed present
               -- with the SAME full paragraph count as a logged-in view
               would show -- on both free and paywalled samples (Clarin
               server-renders the full article HTML regardless of
               subscription status; the paywall is enforced client-side
               via JS/CSS overlay, which is irrelevant to an HTTP-only
               scraper). `#cuerpo` already excludes the "enable
               JavaScript" noscript warning, the "Solo suscriptores"
               paywall badge, and the trailing "Newsletter Clarín" /
               "Edición impresa" CTA blocks that live in sibling DOM
               nodes outside it -- confirmed on 3 samples -- but the
               exact-match filters below are kept as a defense-in-depth
               safety net in case a different article template nests them
               inside `#cuerpo`. Inline dateline/wire-style credit lines
               (e.g. "Misiones. Corresponsalía." / "D.D.") that DO live
               inside `#cuerpo` on some articles are LEFT IN as real
               editorial content, same treatment as "Lee también" in
               eluniversal-scraper.
  Paywall     -- `isAccessibleForFree` is a genuine mixed signal on this
               site (confirmed both `true` and `false` samples in the
               `/opinion/` section; breaking-news sections sampled were
               all free). It is surfaced as `_paywalled` in the output.
               **This never means truncated text** -- the full body is
               present in the HTML regardless, per the paragraph-count
               check above, so `articleBody` is always the complete
               article; `_paywalled` only flags what the subscription
               gate around it would say.
  S2-sitemap  -- Google News sitemap
               (`/sitemaps/sitemap_google_news.xml`, advertised in
               robots.txt). `news:title` is plain text (not CDATA-
               wrapped) so it needs no unescape; `image:caption` IS
               CDATA-wrapped and passed through as-is. No `news:keywords`
               field is present on this sitemap (unlike eluniversal's),
               so `latest` mode output has no keywords field.
"""

import json
from datetime import datetime, timezone

from bs4 import BeautifulSoup

JS_WARNING = "Para disfrutar los contenidos de Clarín es necesario que actives JavaScript en tu navegador."
SUBSCRIBERS_ONLY_BADGE = "Solo suscriptores"
NEWSLETTER_CTA_TITLE = "Newsletter Clarín"
NEWSLETTER_CTA_PREFIX = "Recibí en tu mail"
PRINT_EDITION_FOOTER = "Edición impresa"

BOILERPLATE_EXACT = {JS_WARNING, SUBSCRIBERS_ONLY_BADGE, NEWSLETTER_CTA_TITLE, PRINT_EDITION_FOOTER}


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _has_news_article_type(data: dict) -> bool:
    t = data.get("@type")
    if t == "NewsArticle":
        return True
    if isinstance(t, list) and "NewsArticle" in t:
        return True
    return False


def _find_news_article(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict) and _has_news_article_type(data):
            return data
    return None


def _author_name(author) -> str | None:
    if isinstance(author, list):
        names = [a.get("name") for a in author if isinstance(a, dict) and a.get("name")]
        return ", ".join(names) if names else None
    if isinstance(author, dict):
        return author.get("name")
    return author


def _image_url(image) -> str | None:
    if isinstance(image, list):
        for item in image:
            if isinstance(item, dict) and item.get("url"):
                return item["url"]
        return None
    if isinstance(image, dict):
        return image.get("url")
    return image if isinstance(image, str) else None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    news_article = _find_news_article(soup)
    if news_article is None:
        raise UnexpectedShape("No NewsArticle ld+json block found -- page shape has likely changed.")

    body_el = soup.select_one("#cuerpo")
    if body_el is None:
        raise UnexpectedShape("No #cuerpo element found -- page shape has likely changed.")
    paragraphs = []
    for p in body_el.find_all("p"):
        text = p.get_text(" ", strip=True)
        if not text or text in BOILERPLATE_EXACT or text.startswith(NEWSLETTER_CTA_PREFIX):
            continue
        paragraphs.append(text)
    article_body = "\n\n".join(paragraphs)
    if not article_body:
        raise UnexpectedShape("articleBody parsed to empty text -- page shape has likely changed.")

    keywords = news_article.get("keywords")
    keywords_list = [k.strip() for k in keywords.split(",") if k.strip()] if isinstance(keywords, str) else keywords

    is_accessible_for_free = news_article.get("isAccessibleForFree")

    return {
        "_input": url,
        "_source": "S1-jsonld+html",
        "_scrapedAt": utc_now_iso(),
        "headline": news_article.get("headline"),
        "description": news_article.get("description"),
        "articleBody": article_body,
        "author": _author_name(news_article.get("author")),
        "publisher": _author_name(news_article.get("publisher")),
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "articleSection": news_article.get("articleSection"),
        "keywords": keywords_list,
        "image": _image_url(news_article.get("image")),
        "isAccessibleForFree": is_accessible_for_free,
        "_paywalled": (is_accessible_for_free is False),
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
        image_loc = url_node.find("image:loc")
        image_caption = url_node.find("image:caption")
        items.append(
            {
                "_input": "latest",
                "_source": "S2-sitemap",
                "_scrapedAt": utc_now_iso(),
                "title": title.text.strip() if title and title.text else None,
                "link": loc.text.strip() if loc and loc.text else None,
                "publicationDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "imageUrl": image_loc.text.strip() if image_loc and image_loc.text else None,
                "imageCaption": image_caption.text.strip() if image_caption and image_caption.text else None,
            }
        )
    return items
