"""Whop client -- fetch a storefront page plus each of its plan/checkout
subpages, and pull known fields out of the raw React Server Components
(RSC) streaming payload with targeted regexes.

Whop does NOT ship a clean `__NEXT_DATA__`-style JSON blob like Skool
does -- its Next.js app-router frontend streams `self.__next_f.push([1,
"..."])` chunks using unquoted-key object-literal syntax (e.g.
`memberCount:4541`), which is not valid JSON and can't be `json.loads`'d
directly. This client extracts the specific fields this actor needs via
regex against the raw response text instead of a full RSC/JS parse --
confirmed workable against real storefront/plan pages during recon (see
CRAWLING_METHOD.md), but more fragile to a Whop frontend refactor than a
JSON parse would be: if Whop reorders these object-literal keys, the
regexes below will start returning None instead of raising, since a
"field not found" is expected/common (see `parse_storefront`) rather
than always a bug. If Whop ever ships `__NEXT_DATA__` or a documented
JSON API instead, prefer that.

Real revenue (GMV) does not appear anywhere in the storefront/plan page
payloads probed during recon -- only `memberCount` (all-time member
count, not just paying subscribers) and per-plan pricing are available
unauthenticated. See CRAWLING_METHOD.md.
"""

import asyncio
import json
import re

from curl_cffi.requests import AsyncSession

from src.constants import (
    DEFAULT_HEADERS,
    MAX_RETRIES,
    RETRY_DELAY_BASE,
    TLS_PROFILE,
    WHOP_BASE_URL,
)

_SLUG_RE = re.compile(r"^(?:https?://)?(?:www\.)?whop\.com/", re.IGNORECASE)

BLOCK_MARKERS = [b"Just a moment", b"challenge-platform", b"cf-mitigated", b"captcha-delivery.com"]

_ESCAPED_STR = r'(?:[^"\\]|\\.)*'

_COMPANY_RE = re.compile(
    r'publicCompany:(?:\$R\[\d+\]=)?\{id:"(?P<id>biz_[a-zA-Z0-9]+)",title:"(?P<title>' + _ESCAPED_STR + r')"'
    r',creatorPitch:"(?P<pitch>' + _ESCAPED_STR + r')",route:"(?P<route>[a-zA-Z0-9_-]+)"'
    r',verified:[^,]+,memberCount:(?P<memberCount>\d+)'
)
_REVIEWS_RE = re.compile(r'reviewsAverage:(?P<avg>[\d.]+),publishedReviewsCount:(?P<count>\d+)')
_ACCESS_PASS_RE = re.compile(
    r'\{id:"(?P<id>prod_[a-zA-Z0-9]+)",title:"(?P<title>' + _ESCAPED_STR + r')"'
    r',route:"(?P<route>[a-zA-Z0-9_-]+)",visiblePlansCount:(?P<vpc>\d+)'
)
_PLAN_RE = re.compile(
    r'billingPeriod:(?P<billingPeriod>-?\d+|null),onBehalfOfId:"[^"]*"'
    r',paymentRequestOnBehalfOfId:"[^"]*",rawInitialPrice:(?P<initial>-?[\d.]+)'
    r',rawRenewalPrice:(?P<renewal>-?[\d.]+),planType:"(?P<planType>\w+)"'
)


class NotFound(Exception):
    """HTTP 404 -- slug doesn't resolve to any Whop listing."""


class UnexpectedShape(Exception):
    """The storefront payload didn't contain a recognizable publicCompany
    block -- Whop's page structure changed; investigate before trusting
    further output."""


def extract_slug(raw: str) -> str:
    s = raw.strip()
    s = _SLUG_RE.sub("", s)
    s = s.split("?")[0].split("#")[0]
    return s.strip("/")


def _unescape_js_string(s: str) -> str:
    try:
        return json.loads(f'"{s}"')
    except json.JSONDecodeError:
        return s


def is_blocked(response) -> bool:
    if response.status_code in (403, 407, 429, 503):
        return True
    head = response.content[:8192] if response.content else b""
    return any(m in head for m in BLOCK_MARKERS)


def parse_storefront(text: str, slug: str) -> dict:
    m = _COMPANY_RE.search(text)
    if not m:
        raise UnexpectedShape(f"No publicCompany block found for '{slug}'")

    company = {
        "id": m.group("id"),
        "title": _unescape_js_string(m.group("title")),
        "creatorPitch": _unescape_js_string(m.group("pitch")),
        "route": m.group("route"),
        "memberCount": int(m.group("memberCount")),
    }

    rm = _REVIEWS_RE.search(text)
    if rm:
        company["reviewsAverage"] = float(rm.group("avg"))
        company["publishedReviewsCount"] = int(rm.group("count"))

    access_passes = [
        {
            "id": am.group("id"),
            "title": _unescape_js_string(am.group("title")),
            "route": am.group("route"),
            "visiblePlansCount": int(am.group("vpc")),
        }
        for am in _ACCESS_PASS_RE.finditer(text)
    ]
    # de-dupe by route -- the same accessPass often appears more than
    # once in the RSC stream (once per section that references it)
    seen_routes = set()
    deduped = []
    for ap in access_passes:
        if ap["route"] in seen_routes:
            continue
        seen_routes.add(ap["route"])
        deduped.append(ap)
    company["accessPasses"] = deduped
    return company


def parse_plans(text: str) -> list[dict]:
    plans = []
    for m in _PLAN_RE.finditer(text):
        billing_period = m.group("billingPeriod")
        plans.append(
            {
                "billingPeriodDays": None if billing_period == "null" else int(billing_period),
                "rawInitialPrice": float(m.group("initial")),
                "rawRenewalPrice": float(m.group("renewal")),
                "planType": m.group("planType"),
            }
        )
    return plans


def best_monthly_price_usd(plans: list[dict]) -> float | None:
    """Pick the cheapest *recurring* plan's monthly-equivalent price as
    the representative subscription price. One-time-only plans (planType
    == "one_time" with no renewal) don't feed an MRR estimate."""
    monthly_candidates = []
    for p in plans:
        if p["rawRenewalPrice"] and p["billingPeriodDays"]:
            monthly_candidates.append(p["rawRenewalPrice"] / (p["billingPeriodDays"] / 30))
    if not monthly_candidates:
        return None
    return round(min(monthly_candidates), 2)


class WhopClient:
    def __init__(self, proxy_url: str | None = None, profile: str = TLS_PROFILE):
        self.session = AsyncSession(
            impersonate=profile,
            proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
            timeout=30,
        )
        self.session.headers.update(DEFAULT_HEADERS)

    async def get_community(self, slug: str, max_plan_pages: int = 5) -> dict:
        r = await self._with_retry("GET", f"{WHOP_BASE_URL}/{slug}/")
        if r.status_code == 404:
            raise NotFound(f"'{slug}' -> 404")

        company = parse_storefront(r.text, slug)

        all_plans = []
        seen_plan_keys = set()
        company_route = company["route"]
        for ap in company["accessPasses"][:max_plan_pages]:
            pr = await self._with_retry("GET", f"{WHOP_BASE_URL}/{company_route}/{ap['route']}/")
            if pr.status_code != 200:
                continue
            for p in parse_plans(pr.text):
                p["accessPassRoute"] = ap["route"]
                p["accessPassTitle"] = ap["title"]
                # A single plan-page's RSC payload has been observed to
                # repeat the same plan object more than once (e.g. once
                # in a pricing card, once in a checkout summary widget) --
                # dedupe on the plan's own values, not on position.
                key = (
                    ap["route"],
                    p["billingPeriodDays"],
                    p["rawInitialPrice"],
                    p["rawRenewalPrice"],
                    p["planType"],
                )
                if key in seen_plan_keys:
                    continue
                seen_plan_keys.add(key)
                all_plans.append(p)
        company["plans"] = all_plans
        # Best-effort primary tier: the community's first-listed access
        # pass, used for the single representative subscriptionPrice.
        # NOTE: a sibling access pass's page has been observed to embed
        # ANOTHER pass's price too (e.g. a "kaizen-free" plan page
        # rendering Kaizen Pro's $550 price in an upsell widget) -- so
        # `plans` (all passes, deduped) may contain cross-listed prices
        # that don't belong to the pass they're tagged with. Restricting
        # the MRR estimate to just the primary pass's own page reduces
        # (but does not eliminate) that risk; see CRAWLING_METHOD.md.
        company["primaryAccessPassRoute"] = (
            company["accessPasses"][0]["route"] if company["accessPasses"] else None
        )
        company["plansTruncated"] = len(company["accessPasses"]) > max_plan_pages
        return company

    async def _with_retry(self, method: str, url: str, **kwargs):
        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                r = await self.session.request(method, url, **kwargs)
                if is_blocked(r):
                    await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
                    continue
                return r
            except Exception as e:  # noqa: BLE001 -- network errors are all retryable here
                last_exc = e
                await asyncio.sleep(RETRY_DELAY_BASE * (2**attempt))
        raise RuntimeError(f"Exhausted {MAX_RETRIES} retries for {url}: {last_exc!r}")

    async def close(self):
        await self.session.close()
