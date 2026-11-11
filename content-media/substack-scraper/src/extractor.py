"""Record shaping -- raw passthrough of Substack's own JSON shape plus the
portfolio-standard envelope tags, plus this actor's one derived field that
is the whole point of it: `markdown`.

Per .ai/conventions/dataset-envelope.md, upstream field names are kept
verbatim (no renaming); `markdown` and `content_truncated` are new
top-level fields added alongside the raw payload, not renames of it.
"""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from markdownify import markdownify as md

from src.constants import STRIP_CSS_CLASSES

_POST_URL_RE = re.compile(r"^(?:https?://)?([^/]+)/p/([^/?#]+)", re.IGNORECASE)


def host_from_pub_input(raw: str) -> str:
    """Accepts a bare subdomain ("noahpinion"), a full `*.substack.com` or
    custom-domain host, or a full URL, and returns just the host Substack's
    own `/api/v1/...` endpoints live on (same host as the publication site
    itself -- see CRAWLING_METHOD.md)."""
    s = raw.strip()
    s = re.sub(r"^https?://", "", s, flags=re.IGNORECASE)
    s = s.split("/")[0].split("?")[0]
    if "." not in s:
        s = f"{s}.substack.com"
    return s


def parse_post_url(raw: str) -> tuple[str, str] | None:
    """Extracts (host, slug) from a Substack post URL, e.g.
    "https://noahpinion.substack.com/p/some-slug" or
    "https://www.noahpinion.blog/p/some-slug". Returns None if the URL
    doesn't match Substack's `/p/<slug>` post-URL shape."""
    m = _POST_URL_RE.match(raw.strip())
    if not m:
        return None
    return m.group(1), m.group(2)


def clean_body_html(html: str) -> str:
    """Strips Substack-injected CTA/widget boilerplate (Subscribe/Share/
    Leave-a-comment buttons, inline subscribe widgets) that is not part of
    the author's own writing, so the resulting Markdown is clean prose."""
    # "lxml" auto-wraps a bare fragment in <html><body>...</body></html>;
    # operate on soup.body (falling back to soup itself for other parsers)
    # so the trailing-cleanup below and the returned HTML both stay a plain
    # fragment, not a full document.
    soup = BeautifulSoup(html, "lxml")
    for cls in STRIP_CSS_CLASSES:
        for el in soup.select(f".{cls}"):
            el.decompose()
    root = soup.body or soup
    # Drop now-empty trailing <div><hr></div> dividers left behind once the
    # button(s) they used to separate from the article body are gone.
    while True:
        children = [c for c in root.contents if getattr(c, "name", None)]
        if not children:
            break
        last = children[-1]
        tag_children = [c for c in last.children if getattr(c, "name", None)]
        if last.name == "div" and tag_children and all(c.name == "hr" for c in tag_children) and not last.get_text(strip=True):
            last.decompose()
            continue
        break
    return "".join(str(c) for c in root.contents)


def html_to_markdown(html: str) -> str:
    return md(html, heading_style="ATX", bullets="-", strip=["script", "style", "iframe"]).strip()


def build_post_markdown(post: dict) -> str:
    title = post.get("title") or ""
    subtitle = post.get("subtitle") or ""
    bylines = post.get("publishedBylines") or []
    authors = ", ".join(b["name"] for b in bylines if b.get("name"))
    date = (post.get("post_date") or "")[:10]
    url = post.get("canonical_url") or ""

    lines = [f"# {title}"]
    if subtitle:
        lines.append(f"\n{subtitle}")
    meta_bits = [b for b in (authors, date) if b]
    if meta_bits:
        lines.append("\n*" + " · ".join(meta_bits) + "*")
    if url:
        lines.append(f"\n{url}")
    header = "\n".join(lines)

    body_html = post.get("body_html") or ""
    body_md = html_to_markdown(clean_body_html(body_html)) if body_html else ""
    return f"{header}\n\n---\n\n{body_md}".strip()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def wrap(item: dict, input_value: str, source: str = "S1-api", record_type: str | None = None) -> dict:
    record = {
        "_input": input_value,
        "_source": source,
        "_scrapedAt": utc_now_iso(),
    }
    if record_type:
        record["recordType"] = record_type
    record.update(item)
    return record


def build_post_record(post: dict, input_value: str, record_type: str | None = None) -> dict:
    enriched = dict(post)
    enriched["markdown"] = build_post_markdown(post)
    # Public API only ever returns a free-preview truncation of body_html
    # for paid-only posts (confirmed live -- see constants.py). This flag
    # tells consumers whether `markdown`/`body_html` is the full post.
    enriched["content_truncated"] = post.get("audience") == "only_paid"
    return wrap(enriched, input_value, record_type=record_type)


def build_publication_record(pub: dict, input_value: str) -> dict:
    return wrap(pub, input_value, source="S2-html", record_type="PUBLICATION_PROFILE")


def extract_error(input_value: str, error_kind: str, detail: str = "") -> dict:
    return {
        "_input": input_value,
        "_source": "none",
        "_scrapedAt": utc_now_iso(),
        "_error": error_kind,
        "_errorDetail": detail,
    }
