"""Parsers for LinkedIn's guest HTML.

LinkedIn ships a JSON-LD block on its public profile, company, post and article
pages, and that block is by far the most stable thing on the page -- it survives
the CSS class churn that breaks selector-based scrapers. So everything that can
come from JSON-LD does, and HTML selectors are used only for what JSON-LD omits:
comment bodies, reaction-type breakdowns and job-posting criteria.

Every extractor returns ``None`` or an empty list rather than raising, because a
half-parsed profile is still worth a row and LinkedIn varies its markup by
account type, locale and A/B bucket.
"""

from __future__ import annotations

import html as html_module
import json
import re
from datetime import datetime, timezone
from urllib.parse import unquote
from typing import Any

# Tracking junk LinkedIn appends to every internal link.
_TRACKING_PARAMS = re.compile(r"[?&](trk|trackingId|originalSubdomain|lipi|li[a-z]*)=")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# -- text helpers ---------------------------------------------------------


def html_to_text(fragment: str | None) -> str:
    """Flatten an HTML fragment to readable text, keeping paragraph breaks."""
    if not fragment:
        return ""
    text = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    text = re.sub(r"(?i)</(p|div|li|h[1-6])>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "- ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_module.unescape(text)
    text = text.replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def collapse(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def clean_url(url: str | None) -> str | None:
    """Strip LinkedIn's tracking query and normalise country subdomains.

    Public pages link members as ``in.linkedin.com/in/x`` or
    ``id.linkedin.com/in/x`` depending on where the member sits. Those are the
    same profile as ``www.linkedin.com/in/x``; leaving the variants in means a
    CRM de-duplicates badly, so they are folded onto www here.
    """
    if not url:
        return None
    url = html_module.unescape(url.strip())
    url = url.split("?")[0].split("#")[0]
    url = re.sub(r"^https?://[a-z]{2,3}\.linkedin\.com", "https://www.linkedin.com", url)
    url = re.sub(r"^https?://linkedin\.com", "https://www.linkedin.com", url)
    return url.rstrip("/") or None


def profile_slug(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"/in/([^/?#]+)", url)
    return match.group(1) if match else None


def company_slug(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"/(?:company|school|showcase)/([^/?#]+)", url)
    return match.group(1) if match else None


# Suffixes that are credentials or noise, not surname material.
_NAME_NOISE = {
    "phd", "ph.d", "md", "mba", "cpa", "cfa", "pmp", "msc", "bsc", "ma", "ms",
    "jr", "sr", "ii", "iii", "iv", "mcp", "cissp", "pe", "esq", "rn", "dds",
}


def split_name(full_name: str | None) -> tuple[str | None, str | None]:
    """Split a display name into first and last, dropping credential suffixes.

    LinkedIn display names routinely carry ", PhD" or " (He/Him)" or an emoji
    hiring frame. A mail-merge that greets someone as "Hi Dr, PhD" is worse than
    no personalisation at all, so this trims hard and returns None when the
    remainder is not usable.
    """
    if not full_name:
        return None, None
    name = collapse(full_name)
    name = re.sub(r"\([^)]*\)", " ", name)  # pronouns, nicknames
    name = re.sub(r"[\U0001F000-\U0001FAFF☀-➿]", " ", name)  # emoji frames
    name = name.split("|")[0]
    parts = [p for p in re.split(r"[,\s]+", name) if p]
    cleaned = []
    for part in parts:
        bare = part.strip(".").lower()
        if bare in _NAME_NOISE or (len(part) <= 1 and not part.isalpha()):
            continue
        cleaned.append(part)
    if not cleaned:
        return None, None
    if len(cleaned) == 1:
        return cleaned[0], None
    return cleaned[0], cleaned[-1]


# -- JSON-LD --------------------------------------------------------------

_LD_BLOCK = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.S | re.I
)


def json_ld(page: str) -> list[dict]:
    """Every JSON-LD node on the page, with ``@graph`` containers flattened."""
    nodes: list[dict] = []
    for block in _LD_BLOCK.findall(page or ""):
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue
        for candidate in parsed if isinstance(parsed, list) else [parsed]:
            if not isinstance(candidate, dict):
                continue
            graph = candidate.get("@graph")
            if isinstance(graph, list):
                nodes.extend(node for node in graph if isinstance(node, dict))
            else:
                nodes.append(candidate)
    return nodes


def ld_of_type(nodes: list[dict], *types: str) -> list[dict]:
    wanted = {t.lower() for t in types}
    out = []
    for node in nodes:
        node_type = node.get("@type")
        values = node_type if isinstance(node_type, list) else [node_type]
        if any(str(v).lower() in wanted for v in values):
            out.append(node)
    return out


def meta_content(page: str, name: str) -> str | None:
    pattern = re.compile(
        rf'<meta (?:name|property)="{re.escape(name)}" content="([^"]*)"', re.I
    )
    match = pattern.search(page or "")
    return html_module.unescape(match.group(1)) if match else None


def interaction_count(node: dict, kind: str) -> int | None:
    """Pull one counter out of schema.org ``interactionStatistic``.

    ``kind`` is a fragment such as ``LikeAction`` or ``CommentAction``.
    """
    stats = node.get("interactionStatistic")
    if not stats:
        return None
    for entry in stats if isinstance(stats, list) else [stats]:
        if not isinstance(entry, dict):
            continue
        if kind.lower() in str(entry.get("interactionType", "")).lower():
            value = entry.get("userInteractionCount")
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str) and value.replace(",", "").isdigit():
                return int(value.replace(",", ""))
    return None


# -- people ---------------------------------------------------------------


def _org_entries(value: Any) -> list[dict]:
    if not value:
        return []
    items = value if isinstance(value, list) else [value]
    return [item for item in items if isinstance(item, dict)]


def _role_dates(entry: dict) -> tuple[Any, Any]:
    member = entry.get("member")
    member = member[0] if isinstance(member, list) and member else member
    if not isinstance(member, dict):
        return None, None
    return member.get("startDate"), member.get("endDate")


def _person_headline(page: str, person: dict) -> str | None:
    """The member's real headline, which the Person LD node does not carry.

    LinkedIn puts the badge ("Creator, Top Voice") in
    ``disambiguatingDescription`` and leaves the headline out of JSON-LD
    entirely. It does render it twice in the head: as ``<title>`` in the form
    "Name - Headline | LinkedIn", and as the first clause of the meta
    description before a middle dot. The title is tried first because the meta
    description truncates.
    """
    name = collapse(person.get("name"))
    title = re.search(r"<title>(.*?)</title>", page or "", re.S)
    if title:
        text = collapse(html_module.unescape(title.group(1)))
        text = re.sub(r"\s*\|\s*LinkedIn\s*$", "", text)
        if name and text.lower().startswith(name.lower()):
            remainder = text[len(name) :].lstrip(" -–—|·").strip()
            if remainder:
                return remainder
    description = meta_content(page, "description") or ""
    first_clause = re.split(r"\s[·•]\s", description)[0].strip()
    # Company pages use "Name | 123 followers on LinkedIn"; members do not.
    if first_clause and "followers on LinkedIn" not in first_clause:
        return collapse(first_clause) or None
    return None


def parse_person(page: str) -> dict | None:
    """A public ``/in/{slug}`` page as a flat record.

    Everything here comes from the page's ``Person`` JSON-LD node, which carries
    far more than the visible page header: current and past roles with their
    dates, schools with graduation years, location, languages and the follower
    count. Skills, full work history beyond the LD node and contact details are
    not in the guest page at all.
    """
    nodes = json_ld(page)
    people = ld_of_type(nodes, "Person")
    person = next((p for p in people if p.get("name")), None)
    if not person:
        return None

    url = clean_url(person.get("url") or person.get("sameAs"))
    first, last = split_name(person.get("name"))

    titles = person.get("jobTitle")
    titles = titles if isinstance(titles, list) else ([titles] if titles else [])

    positions = []
    for entry in _org_entries(person.get("worksFor")):
        start, end = _role_dates(entry)
        positions.append(
            {
                "companyName": entry.get("name"),
                "companyUrl": clean_url(entry.get("url")),
                "companySlug": company_slug(entry.get("url")),
                "location": entry.get("location"),
                "startDate": start,
                "endDate": end,
                "isCurrent": end is None,
            }
        )

    education = []
    past_roles = []
    for entry in _org_entries(person.get("alumniOf")):
        start, end = _role_dates(entry)
        record = {
            "organizationName": entry.get("name"),
            "organizationUrl": clean_url(entry.get("url")),
            "startDate": start,
            "endDate": end,
        }
        # alumniOf mixes schools and former employers/board seats; the @type and
        # the /school/ URL shape are what tell them apart.
        is_school = str(entry.get("@type", "")).lower() == "educationalorganization"
        if is_school or "/school/" in str(entry.get("url") or ""):
            education.append(record)
        else:
            past_roles.append(record)

    address = person.get("address") if isinstance(person.get("address"), dict) else {}
    current = next((p for p in positions if p["isCurrent"]), None)

    languages = person.get("knowsLanguage")
    language_names = [
        entry.get("name")
        for entry in _org_entries(languages)
        if isinstance(entry, dict) and entry.get("name")
    ]

    return {
        "headline": _person_headline(page, person),
        "fullName": person.get("name"),
        "firstName": first,
        "lastName": last,
        # disambiguatingDescription is LinkedIn's badge ("Creator, Top Voice"),
        # not the member's headline -- kept, but under its own name.
        "linkedinBadge": collapse(person.get("disambiguatingDescription")) or None,
        "about": collapse(person.get("description")),
        "profileUrl": url,
        "profileSlug": profile_slug(url),
        "photoUrl": person.get("image", {}).get("contentUrl")
        if isinstance(person.get("image"), dict)
        else person.get("image"),
        "jobTitles": titles,
        "currentTitle": titles[0] if titles else None,
        "currentCompany": current.get("companyName") if current else None,
        "currentCompanyUrl": current.get("companyUrl") if current else None,
        "currentCompanySlug": current.get("companySlug") if current else None,
        "locality": address.get("addressLocality"),
        "country": address.get("addressCountry"),
        "followers": interaction_count(person, "FollowAction"),
        "languages": language_names,
        "positions": positions,
        "education": education,
        "pastOrganizations": past_roles,
    }


def parse_organization(page: str) -> dict | None:
    """A public ``/company/{slug}`` page as a flat record."""
    nodes = json_ld(page)
    org = next(
        (o for o in ld_of_type(nodes, "Organization") if o.get("name")), None
    )
    if not org:
        return None
    url = clean_url(org.get("url"))

    # Follower count is not in the LD node -- it only appears in the meta
    # description, as "Name | 4,912,887 followers on LinkedIn".
    followers = None
    description = meta_content(page, "description") or ""
    match = re.search(r"([\d,\.]+)\s+followers", description)
    if match:
        digits = re.sub(r"[^\d]", "", match.group(1))
        followers = int(digits) if digits else None

    headcount = org.get("numberOfEmployees")
    if isinstance(headcount, dict):
        headcount = headcount.get("value") or headcount.get("minValue")

    return {
        "companyName": org.get("name"),
        "companyUrl": url,
        "companySlug": company_slug(url),
        "companyId": company_numeric_id(page),
        "tagline": collapse(org.get("slogan")),
        "description": collapse(org.get("description")),
        "website": next(
            (
                link
                for link in (
                    org.get("sameAs")
                    if isinstance(org.get("sameAs"), list)
                    else [org.get("sameAs")]
                )
                if link and "linkedin.com" not in str(link)
            ),
            None,
        ),
        "logoUrl": org.get("logo", {}).get("contentUrl")
        if isinstance(org.get("logo"), dict)
        else org.get("logo"),
        "followers": followers,
        "employeeCount": headcount,
    }


def company_numeric_id(page: str) -> str | None:
    """LinkedIn's internal company id, needed to facet a people search.

    It is never rendered, but it leaks in the "see all employees" call to action
    as ``facetCurrentCompany=["74126343"]`` (URL-encoded).
    """
    for match in re.finditer(r"facetCurrentCompany(.{0,60})", page or "", re.S):
        window = match.group(1)
        # The link is percent-encoded twice: "=%5B123%5D" arrives as
        # "%3D%255B123%255D". Unquoting twice turns the separators back into
        # plain "=[" and "]" so the id is the only digit run left that matters.
        for _ in range(2):
            window = unquote(window)
        found = re.search(r"[=\[\"',]\s*(\d{4,})", window)
        if found:
            return found.group(1)
    return None


# -- posts ----------------------------------------------------------------

_HASHTAG = re.compile(r"#(\w[\wÀ-ɏ]{1,58})")
_MENTION = re.compile(r"@\[([^\]]+)\]")
_URL_IN_TEXT = re.compile(r"https?://[^\s\)\]]+")


def activity_id(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"(?:activity[-:]|ugcPost[-:])(\d{10,})", url)
    return match.group(1) if match else None


def parse_posts(page: str) -> list[dict]:
    """Recent posts carried in a profile's or company's JSON-LD.

    This is the quiet win of the guest surface: LinkedIn embeds the member's
    last several posts, with full text, timestamp and reaction count, in the
    page it serves to logged-out visitors. No feed pagination, no cookie.
    """
    posts = []
    for node in ld_of_type(json_ld(page), "DiscussionForumPosting"):
        url = clean_url(node.get("url") or node.get("mainEntityOfPage"))
        text = collapse(node.get("text"))
        author = node.get("author") if isinstance(node.get("author"), dict) else {}
        hashtags = sorted({h.lower() for h in _HASHTAG.findall(node.get("text") or "")})
        posts.append(
            {
                "postUrl": url,
                "activityId": activity_id(url),
                "postText": text,
                "postHeadline": collapse(node.get("headline")),
                "publishedAt": node.get("datePublished"),
                "authorName": author.get("name"),
                "authorUrl": clean_url(author.get("url")),
                "reactions": interaction_count(node, "LikeAction"),
                "comments": interaction_count(node, "CommentAction"),
                "shares": interaction_count(node, "ShareAction"),
                "hashtags": hashtags,
                "mentions": _MENTION.findall(node.get("text") or ""),
                "externalLinks": _URL_IN_TEXT.findall(node.get("text") or ""),
                "textLength": len(text),
                "isArticle": bool(node.get("headline")),
            }
        )
    return posts


_POST_BODY = re.compile(
    r'class="[^"]*attributed-text-segment-list__content[^"]*"[^>]*>(.*?)</p>', re.S
)
_POST_ACTOR = re.compile(
    r'data-tracking-control-name="public_post_feed-actor-name"[^>]*>(.*?)</a>', re.S
)
_POST_ACTOR_URL = re.compile(
    r'href="([^"]+)\?trk=public_post_feed-actor-name"', re.S
)


def parse_post_page(page: str) -> dict:
    """The post itself, read from its own permalink page.

    A permalink page does not carry the ``DiscussionForumPosting`` node that
    profile and company pages use for their post lists. It describes the post
    through whichever schema.org type matches the attached media -- VideoObject
    for a video, Article for a shared article, nothing at all for a plain text
    post -- so the body and author are read from the rendered card and the
    timestamp is taken from whichever LD node happens to be there.
    """
    nodes = json_ld(page)
    media_node = next(
        (n for n in nodes if str(n.get("@type")) in
         ("VideoObject", "Article", "NewsArticle", "ImageObject", "DiscussionForumPosting")),
        {},
    )
    media_type = {
        "VideoObject": "VIDEO",
        "ImageObject": "IMAGE",
        "Article": "ARTICLE",
        "NewsArticle": "ARTICLE",
    }.get(str(media_node.get("@type")), "TEXT")

    body = _POST_BODY.search(page)
    text = html_to_text(body.group(1)) if body else collapse(media_node.get("description"))

    actor_name = _POST_ACTOR.search(page)
    actor_url = _POST_ACTOR_URL.search(page)
    creator = media_node.get("creator") if isinstance(media_node.get("creator"), dict) else {}

    engagement = parse_post_engagement(page)
    return {
        "activityId": engagement.get("activityId"),
        "postText": text or None,
        "postHeadline": collapse(media_node.get("headline")) or None,
        "publishedAt": media_node.get("datePublished"),
        "postAuthorName": collapse(html_module.unescape(re.sub(r"<[^>]+>", " ", actor_name.group(1))))
        if actor_name
        else creator.get("name"),
        "postAuthorUrl": clean_url(actor_url.group(1)) if actor_url else clean_url(creator.get("url")),
        "postAuthorFollowers": interaction_count(creator, "FollowAction"),
        "mediaType": media_type,
        "reactions": engagement.get("reactions")
        or interaction_count(media_node, "LikeAction"),
        "comments": engagement.get("comments") or media_node.get("commentCount"),
        "reactionTypes": engagement.get("reactionTypes") or [],
        "hashtags": sorted({h.lower() for h in _HASHTAG.findall(text or "")}),
        "externalLinks": _URL_IN_TEXT.findall(text or ""),
        "textLength": len(text or ""),
    }


_ARTICLE_EL = re.compile(r"<article[^>]*>(.*?)</article>", re.S)

# Chrome lines LinkedIn renders above the body inside the same <article>.
_ARTICLE_CHROME = re.compile(
    r"^(report this article|\+ ?follow|published .{0,40}|sign in|like|comment|share|-)$",
    re.I,
)


def parse_article(page: str) -> dict | None:
    """A ``/pulse/`` article: metadata from JSON-LD, body from the page.

    LinkedIn's ``Article`` node is unusual in two ways worth knowing. Its
    ``name`` is the article title while its ``headline`` is the opening
    excerpt -- the opposite of what the field names suggest -- and its
    ``articleBody`` is always empty, so the body has to come from the rendered
    ``<article>`` element with the title, byline and "Report this article"
    chrome trimmed off the top.
    """
    nodes = json_ld(page)
    article = next(
        (n for n in ld_of_type(nodes, "Article", "NewsArticle", "BlogPosting") if n),
        None,
    )
    if not article:
        return None

    author = article.get("author") if isinstance(article.get("author"), dict) else {}
    title = collapse(article.get("name")) or collapse(article.get("headline"))
    author_name = collapse(author.get("name"))

    body = ""
    element = _ARTICLE_EL.search(page)
    if element:
        lines = [line.strip() for line in html_to_text(element.group(1)).split("\n")]
        # The header block ends at the last chrome marker LinkedIn renders
        # above the body -- "+ Follow", "Published <date>", "Report this
        # article". Cutting after the LAST of those is what gets past the
        # author's own headline, which sits between them and is not fixed text.
        cut = 0
        for index, line in enumerate(lines):
            if _ARTICLE_CHROME.match(line) or (
                title and line.lower() == title.lower()
            ) or (author_name and line.lower() == author_name.lower()):
                cut = index + 1
        body = "\n".join(line for line in lines[cut:]).strip()
        body = re.sub(r"\n{3,}", "\n\n", body)

    excerpt = collapse(article.get("headline"))
    # When the trim overshot and left only the excerpt, prefer the excerpt.
    if excerpt and len(body) < len(excerpt):
        body = excerpt

    words = len(body.split())
    url = clean_url(article.get("url") or article.get("mainEntityOfPage"))
    return {
        "articleTitle": title,
        "articleUrl": url,
        "articleSlug": url.rstrip("/").split("/")[-1] if url else None,
        "excerpt": excerpt,
        "articleText": body or None,
        "wordCount": words,
        "readingTimeMinutes": round(words / 225, 1) if words else None,
        "publishedAt": article.get("datePublished"),
        "modifiedAt": article.get("dateModified"),
        "authorName": author_name,
        "authorUrl": clean_url(author.get("url")),
        "authorSlug": profile_slug(clean_url(author.get("url"))),
        "authorFollowers": interaction_count(author, "FollowAction"),
        "reactions": interaction_count(article, "LikeAction"),
        "comments": article.get("commentCount"),
        "coverImage": article.get("image", {}).get("url")
        if isinstance(article.get("image"), dict)
        else article.get("image"),
        "hashtags": sorted({h.lower() for h in _HASHTAG.findall(body)}),
        "externalLinks": sorted(set(_URL_IN_TEXT.findall(body))),
        "isAccessibleForFree": article.get("isAccessibleForFree"),
    }


_COMMENT_BLOCK = re.compile(r'<section class="comment[ "][^>]*>(.*?)</section>', re.S)
_COMMENT_AUTHOR = re.compile(
    r'class="[^"]*comment__author[^"]*"\s+href="([^"]+)"[^>]*>(.*?)</a>', re.S
)
_COMMENT_HEADLINE = re.compile(
    r'class="[^"]*comment__author-headline[^"]*"[^>]*>(.*?)</', re.S
)
_COMMENT_TEXT = re.compile(r'class="[^"]*comment__text[^"]*"[^>]*>(.*?)</p>', re.S)
_COMMENT_AGE = re.compile(
    r'class="[^"]*comment__duration-since[^"]*"[^>]*>(.*?)</span>', re.S
)


def parse_comments(page: str) -> list[dict]:
    """Commenters on a public post page: identity, headline and comment body.

    Reactors are a different story -- the guest page publishes how many people
    reacted and which reaction types were used, but not who they were. That
    list is Voyager-only.
    """
    out = []
    for block in _COMMENT_BLOCK.findall(page or ""):
        author = _COMMENT_AUTHOR.search(block)
        if not author:
            continue
        url = clean_url(author.group(1))
        name = collapse(html_module.unescape(re.sub(r"<[^>]+>", " ", author.group(2))))
        if not name:
            continue
        first, last = split_name(name)
        headline = _COMMENT_HEADLINE.search(block)
        text = _COMMENT_TEXT.search(block)
        age = _COMMENT_AGE.search(block)
        out.append(
            {
                "engagementType": "COMMENT",
                "fullName": name,
                "firstName": first,
                "lastName": last,
                "headline": collapse(html_to_text(headline.group(1)))
                if headline
                else None,
                "profileUrl": url,
                "profileSlug": profile_slug(url),
                "commentText": html_to_text(text.group(1)) if text else None,
                "commentedAgo": collapse(age.group(1)) if age else None,
            }
        )
    return out


def parse_post_engagement(page: str) -> dict:
    """Reaction and comment counters, plus the reaction-type mix, from a post."""
    reactions = re.search(r'data-num-reactions="(\d+)"', page or "")
    comments = re.search(r'data-num-comments="(\d+)"', page or "")
    types = sorted(set(re.findall(r'data-reaction-type="([A-Z_]+)"', page or "")))
    urn = re.search(r'data-activity-urn="urn:li:activity:(\d+)"', page or "")
    return {
        "reactions": int(reactions.group(1)) if reactions else None,
        "comments": int(comments.group(1)) if comments else None,
        "reactionTypes": types,
        "activityId": urn.group(1) if urn else None,
    }


# -- jobs -----------------------------------------------------------------

# Matched as whole words against the description. Ordered longest-first at use
# time so "React Native" wins over "React".
TECH_TERMS = [
    "Python", "JavaScript", "TypeScript", "Java", "Kotlin", "Swift", "Go", "Golang",
    "Rust", "Ruby", "PHP", "C++", "C#", ".NET", "Scala", "Perl", "Elixir", "Haskell",
    "R", "MATLAB", "Objective-C", "Dart", "Solidity", "COBOL", "VBA", "Bash",
    "React Native", "React", "Angular", "Vue", "Svelte", "Next.js", "Nuxt", "jQuery",
    "Node.js", "Express", "Django", "Flask", "FastAPI", "Spring Boot", "Spring",
    "Laravel", "Rails", "ASP.NET", "Symfony", "NestJS", "Flutter",
    "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Cassandra",
    "DynamoDB", "Oracle", "SQL Server", "SQLite", "Snowflake", "BigQuery",
    "Redshift", "Databricks", "Neo4j", "ClickHouse", "SQL", "NoSQL",
    "AWS", "Azure", "GCP", "Google Cloud", "Kubernetes", "Docker", "Terraform",
    "Ansible", "Jenkins", "GitLab", "GitHub Actions", "CircleCI", "ArgoCD",
    "Helm", "Prometheus", "Grafana", "Datadog", "Splunk", "CloudFormation",
    "Kafka", "RabbitMQ", "Airflow", "Spark", "Hadoop", "Flink", "dbt", "Tableau",
    "Power BI", "Looker", "Qlik", "SAS", "SPSS",
    "TensorFlow", "PyTorch", "Keras", "scikit-learn", "Hugging Face", "LangChain",
    "OpenCV", "NLP", "LLM", "Pandas", "NumPy",
    "GraphQL", "REST", "gRPC", "Microservices", "Kubernetes", "Serverless",
    "Salesforce", "SAP", "HubSpot", "Workday", "ServiceNow", "Shopify", "Magento",
    "Figma", "Sketch", "Adobe XD", "Photoshop", "Illustrator", "AutoCAD", "SolidWorks",
    "Jira", "Confluence", "Git", "Linux", "Unix", "Windows Server",
    "Agile", "Scrum", "Kanban", "SAFe", "DevOps", "CI/CD", "TDD",
    "Excel", "Google Analytics", "SEO", "SEM", "Marketo", "Mailchimp",
]

CERT_PATTERNS = [
    r"\bPMP\b", r"\bCISSP\b", r"\bCISA\b", r"\bCISM\b", r"\bCEH\b", r"\bCPA\b",
    r"\bCFA\b", r"\bACCA\b", r"\bCMA\b", r"\bSHRM-[CS]P\b", r"\bPHR\b", r"\bSPHR\b",
    r"\bAWS Certified[^.,;\n]{0,40}", r"\bAzure [A-Z][a-z]+ Certified\b",
    r"\bGoogle Cloud (?:Professional|Associate)[^.,;\n]{0,40}",
    r"\bCCNA\b", r"\bCCNP\b", r"\bCompTIA [A-Za-z+]+\b", r"\bITIL\b",
    r"\bSix Sigma (?:Green|Black) Belt\b", r"\bCSM\b", r"\bPSM ?I{1,3}\b",
    r"\bPE license\b", r"\bRN license\b", r"\bSeries \d{1,2}\b",
    r"\bSecurity\+\b", r"\bNetwork\+\b", r"\bTS/SCI\b", r"\bsecurity clearance\b",
]

_CURRENCY = r"(?:\$|USD|EUR|GBP|£|€|IDR|Rp|SGD|AUD|CAD|INR|₹)"
_AMOUNT = r"\d{1,3}(?:[,\.]\d{3})*(?:\.\d+)?\s*[KkMm]?"

# Two orderings are common: the symbol leads ("$120,000 - $160,000") or it
# trails ("50K-70K USD"). Both are tried, leading form first.
_SALARY_RANGE = re.compile(
    rf"({_CURRENCY})\s*({_AMOUNT})\s*(?:-|–|—|to)\s*(?:{_CURRENCY})?\s*({_AMOUNT})",
    re.I,
)
_SALARY_RANGE_TRAILING = re.compile(
    rf"({_AMOUNT})\s*(?:-|–|—|to)\s*({_AMOUNT})\s*({_CURRENCY})\b",
    re.I,
)
_SALARY_PERIOD = re.compile(
    r"\b(per hour|hourly|/hr|per year|annually|yearly|/yr|per month|monthly|per week)\b",
    re.I,
)

_REMOTE = re.compile(r"\b(fully remote|100% remote|remote[- ]first|work from home|wfh)\b", re.I)
_HYBRID = re.compile(r"\bhybrid\b", re.I)
_ONSITE = re.compile(r"\b(on[- ]site|onsite|in[- ]office)\b", re.I)


def extract_tech_stack(text: str | None) -> list[str]:
    """Technologies named in a job description, matched as whole words.

    Word boundaries matter more than they look: a bare substring search turns
    "R" into a hit on every "R&D", and "Go" into a hit on "Going". Terms with
    regex-special characters (C++, .NET, C#) get escaped rather than skipped.
    """
    if not text:
        return []

    def pattern_for(term: str) -> str:
        escaped = re.escape(term)
        # \b misbehaves next to +, # and . -- use explicit non-word lookarounds.
        left = r"(?<![\w.+#])"
        right = r"(?![\w+#])" if not term[-1].isalnum() else r"(?![\w])"
        # A one-letter language (R, C) next to & is "R&D", not the language.
        if len(term) == 1:
            right = r"(?![\w&+])"
            left = r"(?<![\w&.])"
        return left + escaped + right

    # Longest first, and each match is blanked out of the working copy so a
    # shorter term only survives if it also appears somewhere on its own. That
    # keeps "React Native" from also reporting "React", while "SQL and
    # PostgreSQL" still reports both.
    remaining = text
    found: list[str] = []
    for term in sorted(TECH_TERMS, key=len, reverse=True):
        regex = re.compile(pattern_for(term), re.I)
        if regex.search(remaining):
            found.append(term)
            remaining = regex.sub(" ", remaining)
    return sorted(set(found))


def extract_certifications(text: str | None) -> list[str]:
    if not text:
        return []
    out = set()
    for pattern in CERT_PATTERNS:
        for match in re.findall(pattern, text, re.I):
            value = collapse(match if isinstance(match, str) else match[0])
            if value:
                out.add(value)
    return sorted(out)


def _to_number(raw: str) -> float | None:
    """Parse an amount, handling both thousand-separator conventions.

    "120,000" and "8.000.000" are the same shape in different locales, and
    Indonesian and most European postings use the dot. A dot is read as a
    thousands separator when it is followed by exactly three digits and is not
    the only separator group's decimal tail -- so "8.000.000" is eight million
    while "1.5" stays one and a half.
    """
    raw = raw.strip()
    multiplier = 1.0
    if raw[-1:].lower() == "k":
        multiplier, raw = 1_000.0, raw[:-1].strip()
    elif raw[-1:].lower() == "m":
        multiplier, raw = 1_000_000.0, raw[:-1].strip()
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        raw = raw.replace(".", "")
    raw = raw.replace(",", "")
    try:
        return float(raw) * multiplier
    except ValueError:
        return None


def extract_salary(text: str | None) -> dict:
    """Pay range mentioned anywhere in the description.

    Most postings have no pay range at all, and of those that do, some state it
    because a pay-transparency law requires it and some bury it in a benefits
    paragraph. The period ("per hour" vs "per year") is captured separately
    because a bare 45,000 means very different things in each.
    """
    empty = {
        "salaryMin": None,
        "salaryMax": None,
        "salaryCurrency": None,
        "salaryPeriod": None,
        "salaryRaw": None,
    }
    if not text:
        return empty
    match = _SALARY_RANGE.search(text)
    if match:
        currency, low_raw, high_raw = match.group(1), match.group(2), match.group(3)
    else:
        match = _SALARY_RANGE_TRAILING.search(text)
        if not match:
            return empty
        low_raw, high_raw, currency = match.group(1), match.group(2), match.group(3)
    low, high = _to_number(low_raw), _to_number(high_raw)
    if low is None or high is None or high < low:
        return empty
    window = text[max(0, match.start() - 60) : match.end() + 60]
    period = _SALARY_PERIOD.search(window)
    return {
        "salaryMin": low,
        "salaryMax": high,
        "salaryCurrency": collapse(currency).upper(),
        "salaryPeriod": collapse(period.group(1)).lower() if period else None,
        "salaryRaw": collapse(match.group(0)),
    }


def extract_workplace(text: str | None) -> str | None:
    if not text:
        return None
    if _REMOTE.search(text):
        return "REMOTE"
    if _HYBRID.search(text):
        return "HYBRID"
    if _ONSITE.search(text):
        return "ONSITE"
    return None


_CRITERIA = re.compile(
    r'criteria-subheader[^>]*>(.*?)</h3>.*?criteria-text[^>]*>(.*?)</span>', re.S
)


def parse_job_criteria(page: str) -> dict:
    """The "Seniority level / Employment type / Job function / Industries" grid."""
    out = {}
    for heading, value in _CRITERIA.findall(page or ""):
        key = collapse(html_module.unescape(re.sub(r"<[^>]+>", "", heading))).lower()
        text = collapse(html_module.unescape(re.sub(r"<[^>]+>", "", value)))
        if not key or not text:
            continue
        mapping = {
            "seniority level": "seniorityLevel",
            "employment type": "employmentType",
            "job function": "jobFunction",
            "industries": "industries",
        }
        out[mapping.get(key, re.sub(r"\W+", "", key.title())[:40])] = text
    return out
