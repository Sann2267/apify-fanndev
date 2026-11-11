"""Parsing for clutch.co.

Extraction order follows `.ai/CLAUDE.md` rule 4: JSON-LD first where it exists.
The profile page carries one ``LocalBusiness`` block with the website, phone,
founding year, full postal address, rating, service catalogue and certifications
-- that is the most redesign-proof layer on the site and it is used verbatim.

Three things JSON-LD does NOT carry, and which the HTML does, so both layers are
read on a profile:

* the summary strip (min project size, hourly rate, headcount, languages,
  timezones) -- the lead attributes the vein actually sells,
* the focus charts (service-line, focus-area and industry splits with percents),
* the per-review detail (project size, project length, and the four sub-ratings).

On the profile page the JSON-LD ``review`` array is NOT the page's review list:
the same profile answered with 16 entries on page 1, 12 on page 2 and 6 on a
page that rendered no reviews at all. Reviews are therefore taken from the HTML
``article.profile-review`` blocks, which carry a stable ``id="review-<id>"``.
"""

import json
import re
import urllib.parse as up
from datetime import datetime, timezone

from selectolax.parser import HTMLParser

from src.constants import BASE, PAID_ROW_TYPES, PINNED_ROW_TYPES, ROW_TYPE_DIRECTORY

PERCENT_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*%\s*(.*)$")
TOOLTIP_RE = re.compile(r"<i>(.*?)</i>", re.S)
REVIEW_ID_RE = re.compile(r"review-(\d+)")
PROVIDER_UUID_RE = re.compile(r"go-to-review/([0-9a-f-]{36})/")
TOTAL_RE = re.compile(r"([\d,]+)\s+Companies", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean(value: str | None) -> str | None:
    if value is None:
        return None
    out = re.sub(r"\s+", " ", value).strip()
    return out or None


def _text(node) -> str | None:
    return clean(node.text()) if node is not None else None


def _attr(node, name: str) -> str | None:
    return clean(node.attributes.get(name)) if node is not None else None


def _meta(scope, itemprop: str) -> str | None:
    return _attr(scope.css_first(f"meta[itemprop={itemprop}]"), "content")


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else None


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    m = re.search(r"\d+(?:\.\d+)?", value)
    return float(m.group(0)) if m else None


def split_percent(value: str | None) -> tuple[float | None, str | None]:
    """'25% Web Development' -> (25.0, 'Web Development')."""
    if not value:
        return None, None
    m = PERCENT_RE.match(value)
    if not m:
        return None, clean(value)
    return float(m.group(1)), clean(m.group(2)) or None


def website_from_redirect(href: str | None) -> str | None:
    """Clutch hides every outbound link behind ``r.clutch.co/redirect``; the real
    destination is the ``u`` query parameter, UTM tags and all."""
    if not href:
        return None
    try:
        query = up.parse_qs(up.urlparse(href).query)
    except ValueError:
        return None
    value = (query.get("u") or [None])[0]
    return clean(value)


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = up.urlparse(url).netloc.lower()
    except ValueError:
        return None
    return host[4:] if host.startswith("www.") else (host or None)


def absolute(href: str | None) -> str | None:
    if not href:
        return None
    if href.startswith("http"):
        return clean(href)
    return clean(up.urljoin(BASE, href))


# -- directory rows --------------------------------------------------------


def _services_from_row(row) -> list[dict]:
    """The services strip is rendered twice: as a bar chart whose tooltips hold
    every entry, and as a visible list that collapses the tail into '+N service'.
    The chart is the complete one, so it is preferred and the list is the fallback.
    """
    out: list[dict] = []
    for span in row.css(".provider__services-chart-item"):
        raw = span.attributes.get("data-tooltip-content") or ""
        m = TOOLTIP_RE.search(raw)
        percent, name = split_percent(clean(m.group(1)) if m else None)
        width = _to_float(span.attributes.get("style"))
        if name:
            out.append({"service": name, "percent": percent if percent is not None else width})
    if out:
        return out
    for item in row.css(".provider__services-list-item-text"):
        percent, name = split_percent(_text(item))
        if name:
            out.append({"service": name, "percent": percent})
    return out


def row_record(row, category_url: str, page_number: int) -> dict:
    row_type = _attr(row, "data-type")
    title_link = row.css_first("a.provider__title-link")
    profile_url = absolute(_attr(title_link, "href"))
    rating_node = row.css_first(".sg-rating__number")
    location_node = row.css_first(".provider__highlights-item.location")
    logo = row.css_first(".provider__logotype img")
    website = website_from_redirect(_attr(row.css_first("a.website-link__item"), "href"))
    summary = _text(row.css_first(".provider__description-text-more"))
    verified = row.css_first(".provider__verified-mark")

    # The location cell prints "City, ST" while the microdata beside it carries
    # the parts separately. Both are emitted: the string is what the page shows,
    # the parts are what a CRM can filter on.
    record = {
        "recordType": "PROVIDER",
        "providerId": _attr(row, "data-clutch-pid"),
        "name": _attr(row, "data-title"),
        "profileUrl": profile_url,
        "profileSlug": profile_url.rstrip("/").rsplit("/", 1)[-1] if profile_url else None,
        "website": website,
        "websiteDomain": domain_of(website),
        "logoUrl": _attr(logo, "src"),
        "tagline": _text(row.css_first(".provider__tagline")),
        "summary": summary,
        # placement -----------------------------------------------------
        "rowType": row_type,
        "positionOnPage": _to_int(_attr(row, "data-position")),
        "pageNumber": page_number,
        "isPaidPlacement": row_type in PAID_ROW_TYPES,
        "isPinnedBlock": row_type in PINNED_ROW_TYPES,
        "isRankedResult": row_type == ROW_TYPE_DIRECTORY,
        # reputation ----------------------------------------------------
        "rating": _to_float(_text(rating_node)),
        "ratingValue": _to_float(_meta(row, "ratingValue")),
        "reviewCount": _to_int(_meta(row, "reviewCount")),
        "isVerified": verified is not None,
        "verificationLabel": _attr(verified, "class"),
        # lead attributes -----------------------------------------------
        "minProjectSize": _text(row.css_first(".provider__highlights-item.min-project-size")),
        "hourlyRate": _text(row.css_first(".provider__highlights-item.hourly-rate")),
        "priceRange": _meta(row, "priceRange"),
        "employees": _text(row.css_first(".provider__highlights-item.employees-count")),
        "location": _text(location_node),
        "addressLocality": _meta(row, "addressLocality"),
        "addressRegion": _meta(row, "addressRegion"),
        "addressCountry": _meta(row, "addressCountry"),
        "postalCode": _meta(row, "postalCode"),
        "streetAddress": _meta(row, "streetAddress"),
        "telephone": _meta(row, "telephone"),
        "services": _services_from_row(row) or None,
        "categoryUrl": category_url,
    }
    # The highlight cells repeat their own label when the tooltip is inlined;
    # strip the icon text that selectolax folds into the cell.
    for key in ("minProjectSize", "hourlyRate", "employees", "location"):
        value = record.get(key)
        if value:
            record[key] = clean(value)
    return record


def parse_directory(html: str, category_url: str, page_number: int) -> dict:
    """One category page -> rows plus the page-level facts worth reporting."""
    tree = HTMLParser(html)
    rows = tree.css(".provider-row")
    records = [row_record(r, category_url, page_number) for r in rows]

    title = _text(tree.css_first("title"))
    total_match = TOTAL_RE.search(html)
    pager = tree.css_first(".sg-pagination-v2")
    pages = sorted({int(x) for x in re.findall(r"[?&]page=(\d+)", pager.html)} if pager else set())

    return {
        "records": records,
        "pageTitle": title,
        "totalCompaniesClaim": _to_int(total_match.group(1)) if total_match else None,
        "lastPageInPager": pages[-1] if pages else None,
        "rowCount": len(records),
        "rankedCount": sum(1 for r in records if r["isRankedResult"]),
        "pinnedCount": sum(1 for r in records if r["isPinnedBlock"]),
        "paidCount": sum(1 for r in records if r["isPaidPlacement"]),
    }


# -- profile ---------------------------------------------------------------


def _ldjson(tree) -> dict:
    for node in tree.css('script[type="application/ld+json"]'):
        try:
            payload = json.loads(node.text())
        except ValueError:
            continue
        if isinstance(payload, list):
            payload = next((p for p in payload if isinstance(p, dict)), {})
        if isinstance(payload, dict) and payload.get("@type") in ("LocalBusiness", "Organization"):
            return payload
    return {}


def _summary_details(tree) -> dict:
    """The strip under the profile name: 'Min project size $10,000+', etc.

    The labels are read as text rather than by class, because the wrapper class
    names are Tailwind-style and change between deploys while the labels do not.
    """
    out: dict[str, str | None] = {}
    block = tree.css_first(".profile-summary__details")
    if block is None:
        return out
    for item in block.css("li, div"):
        label = _text(item.css_first("dt, .title, .label"))
        value = _text(item.css_first("dd, .value"))
        if label and value:
            out[label] = value
    if out:
        return out
    # Fallback: the whole strip as one string, split on the known labels.
    text = _text(block) or ""
    labels = [
        "Min project size",
        "Hourly rate",
        "Employees",
        "Locations",
        "Year founded",
        "Languages",
        "Timezones",
    ]
    positions = [(text.find(lb), lb) for lb in labels if text.find(lb) >= 0]
    positions.sort()
    for i, (start, label) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        out[label] = clean(text[start + len(label) : end])
    return out


def _chart_entry(item, group: str | None, group_label: str | None) -> dict:
    link = item.css_first(".chart-legend__item-link")
    return {
        "name": _text(link) or _text(item.css_first(".chart-legend__item-name")),
        "percent": _to_float(_text(item.css_first(".chart-legend__item-percent"))),
        "group": group,
        "groupLabel": group_label,
        "categoryUrl": absolute(_attr(link, "href")),
        "isCertified": "is-certified" in (item.attributes.get("class") or ""),
    }


def _charts(tree) -> dict:
    """Service-line / focus / industry splits, each as [{name, percent, group, ...}].

    The focus tab is not one list: it is eight, one per group (AI Expertise,
    Frameworks, Mobile Platforms, ...), and **each group is its own 100% scale**.
    Flattening them loses that, and the percentages then add up to 800. Every
    entry therefore carries the group it was scaled within, with the readable
    label taken from the group's own dropdown option.
    """
    labels = {
        _attr(node, "value"): _attr(node, "title")
        for node in tree.css("input[name=focus-chart]")
        if _attr(node, "value")
    }
    charts: dict[str, list] = {}
    for tab in tree.css(".chart-legend__tab-content"):
        key = _attr(tab, "data-chart") or "unknown"
        entries = []
        groups = tab.css(".chart-legend__group")
        if groups:
            for group_node in groups:
                group = _attr(group_node, "data-chart")
                for item in group_node.css(".chart-legend__item"):
                    entries.append(_chart_entry(item, group, labels.get(group)))
        else:
            for item in tab.css(".chart-legend__item"):
                entries.append(_chart_entry(item, None, None))
        if entries:
            charts.setdefault(key, []).extend(entries)
    return charts


def parse_profile(html: str, url: str) -> dict:
    tree = HTMLParser(html)
    ld = _ldjson(tree)
    address = ld.get("address") or {}
    rating = ld.get("aggregateRating") or {}
    details = _summary_details(tree)
    charts = _charts(tree)
    uuid_match = PROVIDER_UUID_RE.search(html)

    services = [
        (offer.get("itemOffered") or {}).get("name")
        for offer in (ld.get("hasOfferCatalog") or {}).get("itemListElement") or []
    ]
    credentials = [
        {
            "name": c.get("name"),
            "issuedOn": c.get("dateCreated"),
            "expires": c.get("expires"),
        }
        for c in ld.get("hasCredential") or []
        if isinstance(c, dict)
    ]
    certification = ld.get("hasCertification") or {}

    return {
        "recordType": "PROFILE",
        "profileUrl": url,
        "profileSlug": url.rstrip("/").rsplit("/", 1)[-1].split("?")[0],
        "providerUuid": uuid_match.group(1) if uuid_match else None,
        "name": clean(ld.get("name")) or _text(tree.css_first("h1")),
        "website": clean(ld.get("sameAs")),
        "websiteDomain": domain_of(ld.get("sameAs")),
        "description": clean(ld.get("description")),
        "logoUrl": clean(ld.get("image")),
        "telephone": clean(ld.get("telephone")),
        "foundingDate": clean(str(ld["foundingDate"])) if ld.get("foundingDate") else None,
        "priceRange": clean(ld.get("priceRange")),
        "rating": _to_float(str(rating.get("ratingValue"))) if rating.get("ratingValue") else None,
        "reviewCount": _to_int(str(rating.get("reviewCount"))) if rating.get("reviewCount") else None,
        "bestRating": _to_float(str(rating.get("bestRating"))) if rating.get("bestRating") else None,
        "addressLocality": clean(address.get("addressLocality")),
        "addressRegion": clean(address.get("addressRegion")),
        "addressCountry": clean(address.get("addressCountry")),
        "postalCode": clean(address.get("postalCode")),
        "streetAddress": clean(address.get("streetAddress")),
        "minProjectSize": details.get("Min project size"),
        "hourlyRate": details.get("Hourly rate"),
        "employees": details.get("Employees"),
        "locations": details.get("Locations"),
        "yearFounded": details.get("Year founded"),
        "languages": details.get("Languages"),
        "timezones": details.get("Timezones"),
        "servicesOffered": [clean(s) for s in services if s] or None,
        "serviceLines": charts.get("service_provided") or None,
        "focusAreas": charts.get("focus") or None,
        "industries": charts.get("industries") or None,
        "clientSizes": charts.get("client_size") or charts.get("clients_size") or None,
        "certification": clean(certification.get("name")),
        "certificationStatus": clean(certification.get("certificationStatus")),
        "credentials": credentials or None,
        "reviewsOnPage": len(tree.css("article.profile-review")),
        "hasLdJson": bool(ld),
    }


# -- reviews ---------------------------------------------------------------


def _review_metrics(article) -> dict:
    metrics = {}
    for dl in article.css(".profile-review__rating-metrics dl"):
        label = _text(dl.css_first("dt"))
        value = _to_float(_text(dl.css_first("dd")))
        if label:
            metrics[label] = value
    return metrics


def _review_data_items(article) -> dict:
    """The three-icon strip: Services / Project size / Project length. Each cell
    names itself in ``data-tooltip-content`` -- read the label, never position,
    because a review without a project size drops the cell entirely."""
    out: dict[str, str | None] = {}
    for item in article.css(".data--item"):
        raw = item.attributes.get("data-tooltip-content") or ""
        m = TOOLTIP_RE.search(raw)
        label = clean(m.group(1)) if m else None
        if not label:
            continue
        if label.lower().startswith("service"):
            out["services"] = [
                _text(s) for s in item.css(".profile-review__data-item") if _text(s)
            ] or None
        else:
            out[label] = _text(item)
    return out


def parse_reviews(html: str, url: str, page_number: int) -> list[dict]:
    tree = HTMLParser(html)
    ld = _ldjson(tree)
    provider = clean(ld.get("name"))
    uuid_match = PROVIDER_UUID_RE.search(html)
    slug = url.rstrip("/").rsplit("/", 1)[-1].split("?")[0]

    out = []
    for article in tree.css("article.profile-review"):
        node_id = article.attributes.get("id") or ""
        review_id = article.attributes.get("data-review-id")
        if not review_id:
            m = REVIEW_ID_RE.search(node_id)
            review_id = m.group(1) if m else None
        data = _review_data_items(article)
        metrics = _review_metrics(article)
        reviewer = article.css_first(".profile-review__reviewer")
        out.append(
            {
                "recordType": "REVIEW",
                "reviewId": review_id,
                "profileUrl": url.split("?")[0],
                "profileSlug": slug,
                "providerName": provider,
                "providerUuid": uuid_match.group(1) if uuid_match else None,
                "pageNumber": page_number,
                "title": _text(article.css_first(".profile-review__header h3")),
                "isFeatured": "profile-review__featured" in (article.attributes.get("class") or ""),
                "rating": _to_float(_text(article.css_first(".profile-review__rating .sg-rating__number"))),
                "ratingQuality": metrics.get("Quality"),
                "ratingSchedule": metrics.get("Schedule"),
                "ratingCost": metrics.get("Cost"),
                "ratingWillingToRefer": metrics.get("Willing to Refer"),
                "services": data.get("services"),
                "projectSize": data.get("Project size"),
                "projectLength": data.get("Project length"),
                "quote": _text(article.css_first(".profile-review__quote")),
                "datePublished": _text(article.css_first(".profile-review__date")),
                "reviewerPosition": _text(reviewer.css_first(".reviewer_position")) if reviewer else None,
                "reviewerName": _text(reviewer.css_first(".reviewer_card--name")) if reviewer else None,
                "isVerifiedReviewer": bool(
                    article.css_first(".profile-review__reviewer-verification-badge")
                ),
                "shareUrl": _attr(article.css_first(".profile-review__share-button"), "data-url"),
            }
        )
    return out


# -- sitemap ---------------------------------------------------------------

LOC_RE = re.compile(r"<loc>(.*?)</loc>", re.S)


def parse_sitemap(xml: str) -> list[str]:
    return [clean(u) for u in LOC_RE.findall(xml) if clean(u)]


def category_record(url: str) -> dict:
    """Split a directory URL into the axes Clutch files it under, so a user can
    tell ``/web-designers/lagos`` (a city cut) from ``/ng/web-designers`` (a
    country cut) without opening either."""
    path = up.urlparse(url).path.strip("/")
    parts = [p for p in path.split("/") if p]
    country = parts[0] if parts and len(parts[0]) == 2 else None
    rest = parts[1:] if country else parts
    return {
        "recordType": "CATEGORY",
        "categoryUrl": url,
        "path": "/" + path,
        "countryCode": country,
        "categorySlug": rest[0] if rest else None,
        "refinements": rest[1:] or None,
        "depth": len(parts),
        "isRootCategory": len(rest) == 1 and country is None,
    }
