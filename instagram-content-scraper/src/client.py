"""Transport for Instagram's logged-out web surface: warm, harvest, replay.

The flow for every mode is the same three steps:

1. **Warm** the entity page (`/<user>/`, `/p/<code>/`, `/explore/locations/...`).
   The response sets the `csrftoken`/`ig_did`/`datr` cookies the GraphQL
   endpoint expects, *and* carries both the first page of data and the query id
   needed to ask for the second. The warm-up is therefore never a wasted
   request -- it is the page-1 fetch.
2. **Harvest** `lsd`, the query id and the query's own variables from that HTML
   (see `relay.py`).
3. **Replay** `POST /api/graphql/` with `{variables, doc_id, lsd}` for each
   subsequent page.

Block detection matches the body, not the status. Instagram answers a throttled
anonymous request with **HTTP 200 carrying a login wall** -- never a 429 -- and
the GraphQL endpoint has a second, quieter failure mode where the status is 200
and the payload is `{"data": {"<root>": null}}`. Both are treated as blocks.
"""

from __future__ import annotations

import asyncio
import json
import logging

from curl_cffi.requests import AsyncSession

from src.constants import (
    GRAPHQL_HEADERS,
    GRAPHQL_URL,
    MAX_RETRIES,
    PAGE_HEADERS,
    REQUEST_TIMEOUT,
    RETRY_DELAY_BASE,
    TLS_PROFILE_LADDER,
)

logger = logging.getLogger(__name__)

# Instagram's throttle and its login wall both arrive as HTTP 200 HTML, so the
# body is the only reliable signal. `caa_login_form_data` is the Relay payload
# of the logged-out login homepage -- the tell that a route we asked for was
# swapped for a sign-in page (hashtag and search routes always do this).
BLOCK_MARKERS = (
    "/accounts/login/",
    "caa_login_form_data",
    "CAAFetaIGLoginHomepageQuery",
    "challenge_required",
    "Please wait a few minutes",
    "login_required",
)

# Markers that mean "this page really is the entity page", checked before a
# body marker is allowed to condemn it -- a legitimate profile page still
# contains a login link in its navigation chrome.
#
# These are deliberately the *data root* names only. A generic Polaris marker
# such as "PolarisLoggedOut" is present on genuine pages AND on the login wall
# Instagram substitutes for a throttled request, so admitting one here made
# `is_blocked_html` answer False for an actual wall -- letting a throttled run
# feed a sign-in page to the parser and report it as a shape change.
CONTENT_MARKERS = (
    "xig_user_by_username",
    "xig_polaris_media",
    "xdt_location_get_web_info",
)

# Instagram serves a missing username, shortcode or location as **HTTP 200**
# carrying its client-side error route, not as a 404. Without this marker a
# deleted account looks exactly like a schema change, and the run would raise a
# false UPSTREAM_SHAPE_CHANGED alarm on what is really a NOT_FOUND. The literal
# string "404" is useless here -- it appears in healthy pages too.
NOT_FOUND_MARKER = "PolarisErrorRoot"


class BlockedError(Exception):
    """Every retry and TLS profile was exhausted while still gated."""


class NotFoundError(Exception):
    """The username, shortcode or location id does not resolve publicly."""


def is_blocked_html(status: int, html: str) -> bool:
    """True when a page response is a wall rather than the entity page."""
    if status in (401, 403, 429, 503):
        return True
    if status == 404:
        return False  # a real 404 is a NotFound, handled by the caller
    if any(marker in html for marker in CONTENT_MARKERS):
        return False
    return any(marker in html for marker in BLOCK_MARKERS)


class InstagramClient:
    """A cookie jar plus a fingerprint, rotated together on a block."""

    def __init__(self, proxy_url: str | None = None, new_proxy_url=None) -> None:
        self._new_proxy_url = new_proxy_url
        self._proxy_url = proxy_url
        self._profile_index = 0
        self.session = self._build_session()

    @property
    def profile(self) -> str:
        return TLS_PROFILE_LADDER[self._profile_index % len(TLS_PROFILE_LADDER)]

    def _build_session(self) -> AsyncSession:
        return AsyncSession(
            impersonate=self.profile,
            proxies=(
                {"http": self._proxy_url, "https": self._proxy_url} if self._proxy_url else None
            ),
            timeout=REQUEST_TIMEOUT,
        )

    async def rotate(self) -> None:
        """Fresh fingerprint and, with a proxy configured, a fresh egress IP.

        Instagram's anonymous throttle is IP-bound far more than it is
        fingerprint-bound, so the proxy rotation is the part that recovers a
        run; the profile rotation is cheap insurance alongside it.
        """
        self._profile_index += 1
        if self._new_proxy_url is not None:
            try:
                self._proxy_url = await self._new_proxy_url()
            except Exception as exc:  # noqa: BLE001 - rotation is best-effort
                logger.warning("Could not rotate proxy session: %s", exc)
        try:
            await self.session.close()
        except Exception:  # noqa: BLE001,S110 - closing a dead session is moot
            pass
        self.session = self._build_session()
        logger.info("Rotated to TLS profile %s", self.profile)

    async def warm(self, url: str) -> str:
        """Load an entity page and keep its cookies. Returns the HTML.

        Raises `NotFoundError` for a genuine 404 and `BlockedError` once the
        retry budget is spent.
        """
        last_reason = "unknown"
        for attempt in range(MAX_RETRIES):
            try:
                response = await self.session.get(url, headers=PAGE_HEADERS)
            except Exception as exc:  # noqa: BLE001 - network flake, retry
                last_reason = f"{type(exc).__name__}: {exc}"
                logger.warning("Warm-up error for %s: %s", url, last_reason)
            else:
                html = response.text or ""
                if response.status_code == 404:
                    raise NotFoundError(f"{url} does not resolve to a public page")
                if NOT_FOUND_MARKER in html and not any(
                    marker in html for marker in CONTENT_MARKERS
                ):
                    raise NotFoundError(
                        f"{url} does not exist (Instagram served its error route "
                        "with HTTP 200)"
                    )
                if not is_blocked_html(response.status_code, html):
                    return html
                last_reason = f"wall behind HTTP {response.status_code}"
                logger.warning(
                    "Blocked warming %s (attempt %d/%d, profile %s)",
                    url, attempt + 1, MAX_RETRIES, self.profile,
                )
                await self.rotate()
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2 ** attempt))
        raise BlockedError(f"Could not load {url} after {MAX_RETRIES} attempts: {last_reason}")

    async def graphql(
        self,
        doc_id: str,
        variables: dict,
        lsd: str,
        referer: str,
        root_key: str,
    ) -> dict:
        """Replay a persisted query. Returns the `data` object.

        `root_key` is not cosmetic: a 200 whose `data[root_key]` is null is the
        endpoint's silent-failure mode and is retried as a block rather than
        returned as an empty result.
        """
        form = {
            "variables": json.dumps(variables, separators=(",", ":")),
            "doc_id": doc_id,
            "lsd": lsd,
        }
        last_reason = "unknown"
        for attempt in range(MAX_RETRIES):
            headers = {
                **GRAPHQL_HEADERS,
                "X-FB-LSD": lsd,
                "Referer": referer,
            }
            csrf = self.session.cookies.get("csrftoken")
            if csrf:
                headers["X-CSRFToken"] = csrf
            try:
                response = await self.session.post(GRAPHQL_URL, data=form, headers=headers)
            except Exception as exc:  # noqa: BLE001 - network flake, retry
                last_reason = f"{type(exc).__name__}: {exc}"
                logger.warning("GraphQL error: %s", last_reason)
            else:
                body = response.text or ""
                if response.status_code == 200 and body.lstrip().startswith("{"):
                    try:
                        payload = json.loads(body)
                    except (ValueError, json.JSONDecodeError):
                        last_reason = "200 with unparseable JSON"
                        payload = None
                    if isinstance(payload, dict):
                        if payload.get("errors"):
                            # A GraphQL-level error is a shape problem, not a
                            # block; surfacing it beats silently retrying.
                            raise BlockedError(
                                f"GraphQL errors: {json.dumps(payload['errors'])[:300]}"
                            )
                        data = payload.get("data")
                        if isinstance(data, dict) and data.get(root_key) is not None:
                            return data
                        last_reason = f"200 but data.{root_key} was null"
                else:
                    last_reason = f"HTTP {response.status_code}, {len(body)} bytes"
                logger.warning(
                    "GraphQL replay rejected (attempt %d/%d, profile %s): %s",
                    attempt + 1, MAX_RETRIES, self.profile, last_reason,
                )
                await self.rotate()
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY_BASE * (2 ** attempt))
        raise BlockedError(f"GraphQL replay failed after {MAX_RETRIES} attempts: {last_reason}")

    async def close(self) -> None:
        try:
            await self.session.close()
        except Exception:  # noqa: BLE001,S110
            pass
