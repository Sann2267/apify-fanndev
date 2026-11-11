"""Parsing logic -- turns raw HTTP responses into dataset-ready records.

Extraction strategy (see CRAWLING_METHOD.md for full recon notes):
  S1-jsonld -- diariolibre.com emits a single `<script type="application/
               ld+json">` block per article page, but it's a `@graph` array
               (not a bare `NewsArticle` dict like tass.com/eluniversal.com.mx,
               and not multiple separate `<script>` tags like clarin.com/
               gulfnews.com) containing a `NewsMediaOrganization`, a
               `WebSite`, and a `NewsArticle` node -- the extractor walks
               the `@graph` list and picks the node whose `@type` is
               `NewsArticle`. That node **carries `articleBody` directly**
               (full text, confirmed 2-4 KB across samples spanning news
               and opinion sections) plus `headline`, `alternativeHeadline`,
               `description`, `keywords` (comma-separated string with a
               trailing comma -- split and empty-filtered), `image`
               (`ImageObject` dict), `datePublished`, `dateModified`,
               `articleSection` (comma-joined string, e.g.
               `"actualidad,educacion"` -- left as the raw string, not
               split, since upstream itself treats it as one taxonomy
               path rather than a tag list), `author` (a single `Person`
               dict, `{"name": ..., "url": ...}` -- no multi-byline array
               observed), `publisher` (`Organization`, always `"Diario
               Libre"`), and `inLanguage`. **No `isAccessibleForFree` field
               at all** on either sampled news or opinion articles, and no
               "suscriptores"/"suscríbete"/paywall marker anywhere in the
               raw HTML -- this outlet appears to be fully open-access (see
               Paywall section in CRAWLING_METHOD.md), so the field is
               simply omitted rather than fabricated.
               **Quirk (not a data-corruption bug):** every text field
               inside the ld+json (`headline`, `alternativeHeadline`,
               `description`, `keywords`, `articleBody`, `author.name`)
               contains literal un-decoded numeric-named HTML entities
               (`&oacute;`, `&aacute;`, `&ntilde;`, ...) embedded directly
               in the JSON string value -- these are NOT JSON escapes
               (`json.loads` already handles those), they're HTML entities
               the CMS writes straight into the JSON payload, so a second
               pass of `html.unescape()` is applied to every text field
               before it's returned. Numbers-with-commas (the clarin-scraper
               corruption pattern: "1,8%" mangled to "18%") were explicitly
               checked on a currency/inflation article with figures like
               "6,716 millones de dólares" and "3,276.5 millones" -- all
               intact, no digit-grouping corruption found here.
               If `articleBody` is ever missing/empty from the ld+json (not
               observed in any sample, defensive fallback only), the
               extractor falls back to the `<meta name="ArticleText"
               content="...">` tag, which independently mirrors the same
               HTML-entity-escaped full text.
  S2-rss      -- `/feed/portada.xml` (front-page feed of a custom,
               WordPress-adjacent RSS 2.0 CMS -- declares `xmlns:media` and
               `xmlns:atom` but no `dc:` namespace). Confirmed **only ~28
               items**, no pagination parameter found -- fewer than a
               typical WordPress `/feed`, so `latest` mode can return fewer
               records than `limit` asks for; this is normal, not an error.
               Each `<item>` carries `title`/`link`/`guid` (a UUID, NOT the
               numeric id in the article URL)/`pubDate` (Spanish month
               abbreviation, e.g. `"Tue, 25 Ago 2026 10:39:00 GMT"` -- NOT
               valid RFC-822 English month names, kept as raw string per
               passthrough), several repeated `<category>` tags carrying a
               `vn` (taxonomy-group) attribute -- `"Categorias"` (section),
               `"Subcategorias"` (subsection), `"Autores"` (byline),
               `"Lugares"` (place tag), `"Temas"` (topic tags, repeatable),
               and `"PrincipalTema"` (the lead topic tag) -- and a
               `<media:content url="...">` block with a nested
               `<media:title>` caption. **The `<description
               readingtime="N">` element is CDATA-wrapped HTML containing
               the FULL article body** (`<p>`/`<strong>` markup, verified
               byte-for-byte equivalent in substance to the same article's
               ld+json `articleBody`, not a short teaser like kyivpost's/
               gulfnews's RSS) -- unlike those feeds, this one already
               contains the complete story text, so it is parsed into
               plain paragraphs the same way an HTML `articleBody` would
               be, and exposed as `articleBody`. `readingtime` (whole
               minutes) is surfaced as `readingTime`. Unlike the ld+json
               path, the CDATA content is raw UTF-8 (not HTML-entity-
               escaped) and the non-CDATA element text uses numeric XML
               entities (`&#243;`) -- both are already correctly decoded
               by the XML parser, so no extra `html.unescape()` pass is
               needed for RSS-sourced fields.
"""

import html
import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

ARTICLE_SCRIPT_TYPE = "application/ld+json"

# get_text(" ", strip=True) inserts a space between sibling text nodes --
# harmless between words, but leaves a stray space before punctuation when a
# <strong>word</strong> tag is immediately followed by a comma/period text
# node (confirmed in the RSS CDATA fragments, e.g. "Padres , madres ,").
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?])")


def _tidy_punctuation(text: str) -> str:
    return _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)


class UnexpectedShape(Exception):
    """Upstream HTML/JSON shape changed in a way we don't recognize."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _unescape(value):
    """Undo the CMS's habit of embedding literal HTML entities in JSON string values."""
    if isinstance(value, str):
        return html.unescape(value)
    return value


def _find_news_article(soup: BeautifulSoup) -> dict | None:
    for tag in soup.find_all("script", attrs={"type": ARTICLE_SCRIPT_TYPE}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        # diariolibre.com wraps everything in a single `{"@graph": [...]}`
        # envelope -- but tolerate a bare list or a bare NewsArticle dict too,
        # in case the CMS ever emits a simpler shape on some template.
        if isinstance(data, dict) and isinstance(data.get("@graph"), list):
            candidates = data["@graph"]
        elif isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            candidates = [data]
        else:
            continue
        for node in candidates:
            if isinstance(node, dict) and node.get("@type") == "NewsArticle":
                return node
    return None


def _meta_content(soup: BeautifulSoup, name: str) -> str | None:
    tag = soup.find("meta", attrs={"name": name})
    return tag.get("content") if tag else None


def _author_name(author) -> str | None:
    if isinstance(author, list):
        names = [a.get("name") for a in author if isinstance(a, dict) and a.get("name")]
        return ", ".join(_unescape(n) for n in names) if names else None
    if isinstance(author, dict):
        return _unescape(author.get("name"))
    return _unescape(author)


def _image_url(image) -> str | None:
    if isinstance(image, dict):
        return image.get("url")
    if isinstance(image, list):
        for item in image:
            if isinstance(item, dict) and item.get("url"):
                return item["url"]
        return None
    return image if isinstance(image, str) else None


def _split_keywords(keywords) -> list | None:
    if not isinstance(keywords, str):
        return keywords
    parts = [_unescape(k.strip()) for k in keywords.split(",")]
    parts = [k for k in parts if k]
    return parts or None


def extract_article(html_text: str, url: str) -> dict:
    soup = BeautifulSoup(html_text, "lxml")

    news_article = _find_news_article(soup)
    if news_article is None:
        raise UnexpectedShape("No NewsArticle node found in ld+json @graph -- page shape has likely changed.")

    article_body = news_article.get("articleBody")
    source = "S1-jsonld"
    if not article_body:
        # Defensive fallback -- not observed in recon samples, but the CMS
        # independently mirrors the full text into a meta tag.
        article_body = _meta_content(soup, "ArticleText")
        source = "S1-jsonld+meta-fallback"
    if not article_body:
        raise UnexpectedShape("articleBody missing from both ld+json NewsArticle node and meta[name=ArticleText].")
    article_body = _unescape(article_body)

    publisher = news_article.get("publisher") or {}
    publisher_name = publisher.get("name") if isinstance(publisher, dict) else publisher

    main_entity = news_article.get("mainEntityOfPage") or {}
    canonical_url = main_entity.get("@id") if isinstance(main_entity, dict) else None

    return {
        "_input": url,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
        "headline": _unescape(news_article.get("headline")),
        "alternativeHeadline": _unescape(news_article.get("alternativeHeadline")),
        "description": _unescape(news_article.get("description")),
        "articleBody": article_body,
        "author": _author_name(news_article.get("author")),
        "publisher": _unescape(publisher_name),
        "articleSection": news_article.get("articleSection"),
        "keywords": _split_keywords(news_article.get("keywords")),
        "datePublished": news_article.get("datePublished"),
        "dateModified": news_article.get("dateModified"),
        "image": _image_url(news_article.get("image")),
        "inLanguage": news_article.get("inLanguage"),
        "canonicalUrl": canonical_url,
    }


def extract_error(url: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": url,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }


def _rss_body_from_cdata(description_tag) -> str | None:
    """The CDATA payload is itself an HTML fragment holding the full article
    body -- parse it the same way an HTML articleBody would be parsed."""
    if description_tag is None or not description_tag.string:
        return None
    fragment_soup = BeautifulSoup(str(description_tag.string), "lxml")
    paragraphs = [_tidy_punctuation(p.get_text(" ", strip=True)) for p in fragment_soup.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    if paragraphs:
        return "\n\n".join(paragraphs)
    # No <p> tags found (short brief) -- fall back to raw text of the fragment.
    text = _tidy_punctuation(fragment_soup.get_text(" ", strip=True))
    return text or None


def _categories_by_group(item) -> dict:
    groups: dict[str, list[str]] = {}
    for cat in item.find_all("category"):
        vn = cat.get("vn")
        text = cat.text.strip() if cat.text else None
        if not vn or not text:
            continue
        groups.setdefault(vn, []).append(text)
    return groups


def extract_rss_items(xml_text: str) -> list[dict]:
    soup = BeautifulSoup(xml_text, "xml")
    items = soup.find_all("item")
    if not items:
        raise UnexpectedShape("No <item> elements found in RSS feed -- feed shape has likely changed.")
    results = []
    for item in items:
        title = item.find("title")
        link = item.find("link")
        guid = item.find("guid")
        pub_date = item.find("pubDate")
        description_tag = item.find("description")
        media_content = item.find("media:content")
        media_title = item.find("media:title")

        groups = _categories_by_group(item)

        reading_time = None
        if description_tag is not None and description_tag.get("readingtime"):
            try:
                reading_time = int(description_tag["readingtime"])
            except ValueError:
                reading_time = None

        results.append(
            {
                "_input": "latest",
                "_source": "S2-rss",
                "_scrapedAt": utc_now_iso(),
                "title": _unescape(title.text.strip()) if title and title.text else None,
                "link": link.text.strip() if link and link.text else None,
                "guid": guid.text.strip() if guid and guid.text else None,
                "pubDate": pub_date.text.strip() if pub_date and pub_date.text else None,
                "category": _unescape((groups.get("Categorias") or [None])[0]),
                "subcategory": _unescape((groups.get("Subcategorias") or [None])[0]),
                "author": _unescape((groups.get("Autores") or [None])[0]),
                "place": _unescape((groups.get("Lugares") or [None])[0]),
                "topics": [_unescape(t) for t in groups.get("Temas") or []] or None,
                "principalTopic": _unescape((groups.get("PrincipalTema") or [None])[0]),
                "articleBody": _rss_body_from_cdata(description_tag),
                "readingTime": reading_time,
                "image": media_content.get("url") if media_content else None,
                "imageCaption": _unescape(media_title.text.strip()) if media_title and media_title.text else None,
            }
        )
    return results
