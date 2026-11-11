"""Payload -> record logic for every trustradius.com surface. Pure functions, no I/O.

Everything here is found STRUCTURALLY -- by key name or element shape in the
decoded flight tree -- never by position or by CSS-module class hash suffix
(``Review_review__5RC6b`` changes on every deploy; the ``Review_review`` prefix
does not).

Privacy rule for reviewer identity: the review pages ship every reviewer's full
name, photo and LinkedIn URL in the payload, including reviewers who chose to
publish anonymously -- the site simply does not render them. Two flags look
alike and are not: ``reviewer.authorPublic`` is an ACCOUNT setting (true for 7
of 10 reviewers on hubspot-crm page 1), while the per-REVIEW flag -- the
``isPublic`` prop of the author component, ``showPublic`` on the review -- was
true for 1 of those 10, and matches what the review's own page shows. This
Actor follows the per-review flag: name / company / photo / LinkedIn only when
that review is shown publicly, professional attributes (role, department,
company size, industry, experience) always, and anonymous when the flag is
missing.
"""

from __future__ import annotations

import html as htmllib
import json
import re
from datetime import datetime, timezone

from src.flight import class_of, find_key, is_element, parse_rows, resolve, text_of, walk

BASE = "https://www.trustradius.com"


class UnexpectedShape(Exception):
    """The page answered but the data object this parser relies on is gone."""


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean(value):
    """Drop React elements and client-component references from passthrough
    objects: they are rendering instructions, not data."""
    if isinstance(value, list):
        if is_element(value):
            return None
        out = [clean(v) for v in value]
        return [v for v in out if v is not None]
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if not (isinstance(v, list) and is_element(v))}
    if isinstance(value, str) and value.startswith("$L"):
        return None
    return value


_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"<\s*(br|/p|/li|/div|/h\d)\b[^>]*>", re.I)


def html_to_text(fragment: str | None) -> str | None:
    if fragment is None:
        return None
    text = _BLOCK.sub("\n", fragment)
    text = htmllib.unescape(_TAG.sub("", text))
    text = re.sub(r"[ \t ]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def _largest(rows, key, require: tuple[str, ...] = ()):
    for value in find_key(rows, key):
        value = resolve(value, rows)
        if isinstance(value, dict) and all(k in value for k in require):
            return value
    return None


# -- reviewer privacy --------------------------------------------------------

_ALWAYS = ("title", "jobType", "department", "industryType", "companySize", "yearsExperience")
_PUBLIC_ONLY = ("fullName", "firstName", "lastName", "companyName", "reviewAuthorImageUrl", "linkedInProfileUrl")


def public_reviewer(reviewer: dict | None, shown_publicly) -> dict | None:
    """``shown_publicly`` is the per-review flag; ``authorPublic`` is ignored."""
    if not isinstance(reviewer, dict):
        return None
    is_public = shown_publicly is True
    out = {"isPublic": is_public}
    for key in _ALWAYS:
        if key in reviewer:
            out[key] = reviewer[key]
    if is_public:
        for key in _PUBLIC_ONLY:
            if reviewer.get(key):
                out[key] = reviewer[key]
    verification = reviewer.get("verification")
    if isinstance(verification, dict):
        out["verification"] = verification
    return out


# -- categories (/categories) ----------------------------------------------------


def parse_categories(stream: str) -> list[dict]:
    rows = parse_rows(stream)
    tree = None
    for value in find_key(rows, "categories"):
        value = resolve(value, rows)
        if isinstance(value, list) and value and isinstance(value[0], dict) and "children" in value[0]:
            tree = value
            break
    if not tree:
        raise UnexpectedShape("no category tree on /categories")

    by_slug: dict[str, dict] = {}

    def visit(node: dict, parents: list[dict], group: str):
        slug = node.get("slug")
        children = node.get("children") or []
        is_group = not parents  # the 19 roots are navigation groups, not listable categories
        if slug and not is_group:
            rec = by_slug.get(slug)
            if rec is None:
                rec = {
                    "categoryId": node.get("_id"),
                    "slug": slug,
                    "name": node.get("name"),
                    "description": html_to_text(node.get("description")) if node.get("description") else None,
                    "url": f"{BASE}/categories/{slug}",
                    "parentSlug": parents[-1].get("slug") if len(parents) > 1 else None,
                    "parentName": parents[-1].get("name") if len(parents) > 1 else None,
                    "path": [p.get("name") for p in parents[1:]] + [node.get("name")],
                    "depth": len(parents),
                    "childCount": len(children),
                    "featured": bool(node.get("featured")),
                    "groups": [],
                }
                by_slug[slug] = rec
            if group not in rec["groups"]:
                rec["groups"].append(group)
        for child in children:
            if isinstance(child, dict):
                visit(child, parents + [node], group)

    for root in tree:
        visit(root, [], root.get("name") or root.get("slug") or "")
    return list(by_slug.values())


# -- category listing (/categories/<slug>?f=) ---------------------------------------


def parse_category_page(stream: str) -> tuple[dict, list[dict], dict | None]:
    """Returns (meta, products, category). ``meta`` is None-safe: past the
    offset ceiling the page renders without ``initialData`` at all."""
    rows = parse_rows(stream)
    data = _largest(rows, "initialData", require=("products",))
    category = _largest(rows, "category", require=("_id", "slug"))
    if data is None:
        return {"from": None, "size": 0, "total": None, "missing": True}, [], clean(category)
    return data.get("meta") or {}, [clean(p) for p in data.get("products") or []], clean(category)


def category_product_record(product: dict, category: dict | None, rank: int | None, filters: dict) -> dict:
    slug = product.get("slug")
    vendor = product.get("vendor") or {}
    rating = product.get("rating") or {}
    return {
        "rank": rank,
        "categorySlug": (category or {}).get("slug"),
        "categoryName": (category or {}).get("name"),
        "filters": filters or None,
        "productId": product.get("_id"),
        "slug": slug,
        "name": product.get("name"),
        "url": f"{BASE}/products/{slug}" if slug else None,
        "vendorName": vendor.get("name"),
        "trScore": rating.get("trScore"),
        "ratingAvg": rating.get("avg"),
        "ratingCount": rating.get("count"),
        "reviewCount": (rating.get("reviewsRating") or {}).get("count"),
        "startingPrice": (product.get("startingPrice") or {}).get("price"),
        "trialAvailable": product.get("trialAvailable"),
        "product": product,
    }


# -- product overview (/products/<slug>) -----------------------------------------


def parse_product_page(stream: str) -> dict:
    rows = parse_rows(stream)
    product = _largest(rows, "product", require=("slug", "name", "rating"))
    if product is None:
        raise UnexpectedShape("no product object on the product page")
    product = clean(product)
    for interview in product.get("interviews") or []:
        if isinstance(interview, dict) and "reviewer" in interview:
            interview["reviewer"] = public_reviewer(interview.get("reviewer"), interview.get("showPublic"))
    return product


def parse_pricing_page(stream: str) -> dict:
    rows = parse_rows(stream)
    product = _largest(rows, "product", require=("slug", "editionPricing"))
    if product is None:
        raise UnexpectedShape("no product object on the pricing page")
    product = clean(product)
    keep = (
        "editionPricing", "startingPrice", "freeAvailable", "trialAvailable", "deploymentTypes",
        "miscPricingInfo", "support", "pricingUrl", "pricingAlternatives", "operatingSystems",
        "pricingQuotes",
    )
    out = {k: product.get(k) for k in keep if k in product}
    for quote in out.get("pricingQuotes") or []:
        if not isinstance(quote, dict):
            continue
        reviewer = public_reviewer(quote.get("reviewer"), quote.get("showPublic"))
        quote["reviewer"] = reviewer
        if quote.get("showPublic") is not True:
            quote.pop("author", None)
            quote.pop("company", None)
    return out


# -- reviews list (/products/<slug>/reviews?page=N) --------------------------------


def _answer(node) -> dict:
    """One ReviewAnswer block: a heading plus either HTML or a bullet list."""
    heading, html, items, kind = None, None, None, None
    for sub, _ in walk(node[3]):
        if isinstance(sub, dict):
            inner = sub.get("dangerouslySetInnerHTML")
            if isinstance(inner, dict) and html is None:
                html = inner.get("__html")
            if isinstance(sub.get("items"), list) and items is None:
                items, kind = sub["items"], sub.get("type")
            if sub.get("as") in ("h3", "h4") and heading is None:
                heading = text_of(sub.get("children"))
    return {"question": heading, "type": kind or ("text" if html is not None else None),
            "text": html_to_text(html), "html": html, "items": items}


def parse_reviews_page(stream: str) -> tuple[dict, list[dict]]:
    rows = parse_rows(stream)
    header = {}
    totals = [v for v in find_key(rows, "totalReviews") if isinstance(v, int)]
    header["totalReviews"] = totals[0] if totals else None
    product = _largest(rows, "product", require=("slug", "name"))
    if product:
        header["product"] = {k: product.get(k) for k in ("id", "slug", "name") if k in product}

    reviews, seen = [], set()
    for row in rows.values():
        if not isinstance(row, (list, dict)):
            continue
        for node, anc in walk(row):
            if not (is_element(node) and node[1] == "article" and class_of(node).startswith("Review_review")):
                continue
            wrapper = anc[-2] if len(anc) >= 2 and is_element(anc[-2]) else None
            review_id = wrapper[2] if wrapper and isinstance(wrapper[2], str) else None
            art = resolve(node, rows)
            rec = {"reviewId": review_id, "slug": None, "url": None, "title": None, "rating": None,
                   "datePublished": None, "source": None, "reviewer": None, "verification": None,
                   "pros": None, "cons": None, "answers": []}
            for sub, _ in walk(art):
                if is_element(sub):
                    props = sub[3]
                    cls = class_of(sub)
                    if sub[1] == "a" and str(props.get("href", "")).startswith("/reviews/") and rec["slug"] is None:
                        rec["slug"] = props["href"].split("/reviews/", 1)[1]
                        rec["url"] = BASE + props["href"]
                        rec["title"] = text_of(props.get("children"))
                    elif sub[1] == "time" and rec["datePublished"] is None:
                        rec["datePublished"] = props.get("dateTime")
                    elif "ReviewAnswer_reviewAnswer" in cls and "__html" not in cls:
                        ans = _answer(sub)
                        if ans["type"] == "pros":
                            rec["pros"] = ans["items"]
                        elif ans["type"] == "cons":
                            rec["cons"] = ans["items"]
                        rec["answers"].append(ans)
                elif isinstance(sub, dict):
                    if str(sub.get("id", "")).endswith("_rating") and "value" in sub and rec["rating"] is None:
                        rec["rating"] = sub.get("value")
                    elif "trusted" in sub and "incentive" in sub and rec["source"] is None:
                        rec["source"] = {k: sub.get(k) for k in ("trusted", "incentive", "source")}
                    elif "reviewer" in sub and rec["reviewer"] is None:
                        rec["reviewer"] = public_reviewer(sub.get("reviewer"), sub.get("isPublic"))
                    elif "isVetted" in sub and rec["verification"] is None:
                        rec["verification"] = {k: sub.get(k) for k in ("isVerified", "isVetted", "isReseller")}
            key = rec["reviewId"] or rec["slug"]
            if key and key not in seen:
                seen.add(key)
                reviews.append(rec)
    return header, reviews


# -- single review (/reviews/<slug>, legacy app) ------------------------------------

_BS = chr(92)
_JS_HEX = re.compile(_BS + _BS + "x([0-9a-fA-F]{2})")


def _js_json(text: str):
    """Decode a JSON value that a legacy page wrote into JS with ``\\xNN`` escapes."""
    text = _JS_HEX.sub(lambda m: _BS + "u00" + m.group(1), text.lstrip())
    return json.JSONDecoder().raw_decode(text)[0]


def _view_data(html: str) -> dict:
    start = html.find("window.viewData = {")
    if start < 0:
        raise UnexpectedShape("no window.viewData on the review page")
    body = html[start : html.find("</script>", start)]
    out = {}
    for m in re.finditer(r"\n  ([A-Za-z_]+): ", body):
        try:
            out[m.group(1)] = _js_json(body[m.end() :])
        except ValueError:
            continue
    return out


def _feature_names(value, acc: dict) -> dict:
    for node, _ in walk(value):
        if isinstance(node, dict) and "_id" in node and "name" in node and "isReviewable" in node:
            acc[node["_id"]] = node["name"]
    return acc


def parse_review_detail(html: str) -> dict:
    view = _view_data(html)
    review = view.get("review")
    if not isinstance(review, dict) or "sections" not in review:
        raise UnexpectedShape("window.viewData.review has no sections")
    names: dict = {}
    for value in view.values():
        _feature_names(value, names)
    # The feature catalogue (id -> name) lives in a second blob,
    # window.__INITIAL_DATA__. That blob also carries internal fields (the
    # claiming user's e-mail, admin edit trails), so ONLY the name map and a
    # few dates are read from it -- nothing else is passed through.
    initial = {}
    marker = "window.__INITIAL_DATA__ = "
    start = html.find(marker)
    if start >= 0:
        try:
            initial = (json.JSONDecoder().raw_decode(html[start + len(marker) :])[0] or {}).get("review") or {}
        except ValueError:
            initial = {}
        _feature_names(initial, names)

    details = []
    for section in review.get("sections") or []:
        for q in section.get("questions") or []:
            resp = q.get("response") or {}
            if not resp.get("published") or resp.get("values") in (None, []):
                continue
            obj = q.get("object") if isinstance(q.get("object"), dict) else {}
            public_q = q.get("publicQuestion")
            if not isinstance(public_q, str) or "{{" in public_q:
                pq = obj.get("publicQuestion")
                public_q = pq[0].get("text") if isinstance(pq, list) and pq and isinstance(pq[0], dict) else None
                if public_q and "{{" in public_q:
                    public_q = q.get("title")
            qtype = q.get("type")
            values = resp["values"]
            if qtype == "features":
                value = [
                    {"featureId": v.get("featureId"), "feature": names.get(v.get("featureId")),
                     "value": v.get("value"), "na": v.get("na")}
                    for v in values if isinstance(v, dict)
                ]
            elif qtype in ("text",):
                value = html_to_text("\n".join(str(v) for v in values))
            elif qtype == "slider" and len(values) == 1:
                value = values[0]
            elif qtype == "multiquestion" and len(values) == 1:
                value = values[0]
            else:
                value = values
            details.append({
                "section": section.get("heading") or section.get("title"),
                "slug": obj.get("slug") or q.get("slug"),
                "question": public_q or q.get("title"),
                "type": qtype,
                "value": value,
            })

    subject = review.get("subject") or {}
    profile = {
        "position": {k: v for k, v in (subject.get("position") or {}).items() if k in ("jobType", "department", "title")},
        "companySize": (subject.get("company") or {}).get("size"),
        "industry": ((subject.get("company") or {}).get("industry") or {}).get("name"),
        "countryCode": (subject.get("location") or {}).get("countryCode"),
        "roles": subject.get("roles"),
        "yearsExperience": subject.get("yearsExperience"),
        "currentExperience": subject.get("currentExperience"),
    }
    return {
        "reviewId": review.get("_id"),
        "heading": review.get("heading"),
        "ratingNormalized": (review.get("rating") or {}).get("normalized"),
        "submittedDate": initial.get("submittedDate"),
        "publishedDate": initial.get("publishedDate"),
        "wordCount": initial.get("wordCount"),
        "reviewerProfile": profile,
        "alsoReviewedProducts": [
            {k: p.get(k) for k in ("slug", "name")} for p in (review.get("products") or [])[1:] if isinstance(p, dict)
        ],
        "details": details,
    }


# -- alternatives (/products/<slug>/competitors, legacy app) ---------------------------


def parse_competitors(html: str) -> tuple[list[dict], dict]:
    marker = "window.__INITIAL_DATA__ = "
    start = html.find(marker)
    if start < 0:
        raise UnexpectedShape("no window.__INITIAL_DATA__ on the competitors page")
    data = json.JSONDecoder().raw_decode(html[start + len(marker) :])[0]
    curated = data.get("competitors") or []
    segments = data.get("trustmapAlternativesSearch") or {}
    return curated, segments


def slim_product(p: dict) -> dict:
    rating = p.get("rating") or {}
    vendor = p.get("vendor") or {}
    slug = p.get("slug")
    return {
        "productId": p.get("_id") or p.get("id"),
        "slug": slug,
        "name": p.get("name"),
        "url": f"{BASE}/products/{slug}" if slug else None,
        "vendorName": vendor.get("name") if isinstance(vendor, dict) else None,
        "homepage": p.get("homepage"),
        "ratingAvg": rating.get("avg"),
        "ratingCount": rating.get("count"),
        "reviewCount": (rating.get("reviewsRating") or {}).get("count"),
        "featureRatings": rating.get("featureRatings"),
        "description": p.get("description"),
    }


# -- compare (/compare-products/<a>-vs-<b>) -------------------------------------------


def _texts_by_testid(node) -> list[tuple[str, str]]:
    out = []
    for sub, _ in walk(node):
        if is_element(sub) and sub[3].get("data-testid"):
            out.append((sub[3]["data-testid"], text_of(sub[3].get("children"))))
    return out


def parse_compare(stream: str) -> dict:
    rows = parse_rows(stream)
    headers = next((resolve(v, rows) for v in find_key(rows, "headers")
                    if isinstance(v, list) and v and isinstance(v[0], dict) and "ratingsCount" in v[0]), None)
    if not headers:
        raise UnexpectedShape("no product headers on the comparison page")
    insights = next((resolve(v, rows) for v in find_key(rows, "products")
                     if isinstance(v, list) and v and isinstance(v[0], dict) and "insights" in v[0]), []) or []
    by_slug = {h["slug"]: dict(h) for h in headers if isinstance(h, dict)}
    for item in insights:
        if item.get("slug") in by_slug:
            by_slug[item["slug"]]["insights"] = item.get("insights")

    feature_groups, meta = [], {}
    pricing: dict[str, list[dict]] = {}
    for row in rows.values():
        if not isinstance(row, (list, dict)):
            continue
        for node, _ in walk(row):
            if not is_element(node):
                continue
            props = node[3]
            if "heading" in props and isinstance(props.get("features"), list) and "products" in props:
                props = resolve(props, rows)
                for p in props.get("products") or []:
                    meta.setdefault(p.get("slug"), p)
                feature_groups.append({
                    "id": props.get("id"),
                    "heading": props.get("heading"),
                    "groupRatings": props.get("headers"),
                    "features": props.get("features"),
                })
            elif node[1] == "td" and isinstance(node[2], str) and node[2] in by_slug:
                pairs = _texts_by_testid(resolve(node, rows))
                editions, current = [], None
                for tid, txt in pairs:
                    if tid == "edition-name":
                        current = {"edition": txt, "price": None, "terms": None}
                        editions.append(current)
                    elif tid == "edition-price" and current is not None:
                        current["price"] = txt
                    elif tid == "edition-terms" and current is not None:
                        current["terms"] = txt
                if editions:
                    pricing.setdefault(node[2], editions)

    for slug, m in meta.items():
        if slug in by_slug:
            for k in ("name", "vendorName", "reviewCount", "averageRating", "logoUrl"):
                by_slug[slug].setdefault(k, m.get(k))
    for slug, editions in pricing.items():
        by_slug[slug]["pricingEditions"] = editions

    answers = next((resolve(v, rows) for v in find_key(rows, "answers")
                    if isinstance(v, list) and v and isinstance(v[0], dict) and "fullHtml" in v[0]), []) or []
    testimonials = []
    for a in answers:
        pub = bool(a.get("isPublic"))
        testimonials.append({
            "productName": a.get("productName"),
            "text": html_to_text(a.get("fullHtml")),
            "reviewer": {
                "isPublic": pub,
                "displayName": a.get("displayName") if pub else None,
                "companyName": a.get("companyName") if pub else None,
                "jobTitle": a.get("jobTitle"),
                "jobType": a.get("jobType"),
                "department": a.get("department"),
                "industryType": a.get("industryType"),
                "companySize": a.get("companySize"),
            },
            "source": a.get("source"),
        })

    return {
        "products": list(by_slug.values()),
        "featureGroups": feature_groups,
        "testimonials": testimonials,
    }
