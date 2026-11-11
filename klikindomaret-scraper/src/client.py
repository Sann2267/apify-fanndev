"""HTTP transport for the klikindomaret API.

Wraps a curl_cffi Firefox-impersonating session, applies the WAF identity
(AWS token header + Cloudflare/AWS cookies), and retries with exponential
backoff. Distinguishes the two block classes so the caller can refresh the
right gate:

* AWS token stale/expired  -> re-mint (cheap, headless)
* Cloudflare clearance gone -> re-bootstrap (Camoufox)
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from curl_cffi.requests import AsyncSession

from src.constants import (
    CF_BLOCK_MARKERS,
    MAX_RETRIES,
    NGINX_403,
    RETRY_DELAY_BASE,
    SITE,
    TLS_PROFILE,
)
from src.waf import WafManager

logger = logging.getLogger(__name__)


class BlockedError(RuntimeError):
    """Raised when a request stays blocked after exhausting retries."""


class ClearanceRequired(RuntimeError):
    """Raised when a route needs a Cloudflare clearance we don't yet hold."""


class UpstreamShapeError(RuntimeError):
    """Raised when a 200 response is not the expected `{status, data}` envelope."""


def _classify_block(status: int, body: bytes) -> str | None:
    """Return 'cloudflare', 'aws', or None (not a block)."""
    head = body[:600]
    if any(m in head for m in CF_BLOCK_MARKERS):
        return "cloudflare"
    if NGINX_403 in head:
        # nginx 403 on a protected route == Cloudflare edge rule (search/result)
        return "cloudflare"
    if status in (401, 403) and b"AwsWafIntegration" in body[:2000]:
        return "aws"
    if status in (401, 403):
        return "aws"
    return None


class KlikClient:
    def __init__(self, waf: WafManager, proxy_url: str | None = None) -> None:
        self.waf = waf
        self._proxy_url = proxy_url
        self._session: AsyncSession | None = None

    def _new_session(self) -> AsyncSession:
        kwargs: dict = {"impersonate": TLS_PROFILE, "timeout": 30}
        if self._proxy_url:
            kwargs["proxies"] = {"http": self._proxy_url, "https": self._proxy_url}
        return AsyncSession(**kwargs)

    async def _ensure_session(self) -> AsyncSession:
        if self._session is None:
            self._session = self._new_session()
        return self._session

    def _headers(self, page: str) -> dict:
        ident = self.waf.identity
        ua = ident.user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) "
            "Gecko/20100101 Firefox/133.0"
        )
        return {
            "User-Agent": ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": SITE + "/",
            "Origin": SITE,
            "x-correlation-id": str(uuid.uuid4()),
            "x-aws-waf-token": ident.aws_token,
            "page": page,
            "apps": json.dumps({"app_version": ua}),
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "sec-fetch-dest": "empty",
        }

    def _apply_cookies(self, session: AsyncSession) -> None:
        ident = self.waf.identity
        if ident.cf_clearance:
            session.cookies.set("cf_clearance", ident.cf_clearance, domain=".klikindomaret.com")
        token = ident.aws_cookie or ident.aws_token
        if token:
            session.cookies.set("aws-waf-token", token, domain=".klikindomaret.com")

    async def get_json(
        self,
        url: str,
        params: dict | None = None,
        page: str = "unpage",
        needs_clearance: bool = False,
    ) -> dict:
        """GET a klikindomaret API route and return its parsed JSON envelope.

        Refreshes the AWS token / Cloudflare clearance and retries on block.
        """
        await self.waf.ensure_aws_token()
        if needs_clearance and not self.waf.identity.has_clearance():
            await self.waf.ensure_clearance()

        session = await self._ensure_session()
        last_detail = ""

        for attempt in range(MAX_RETRIES):
            self._apply_cookies(session)
            try:
                resp = await session.get(url, params=params, headers=self._headers(page))
            except Exception as exc:  # noqa: BLE001
                last_detail = f"transport: {exc!r}"
                await asyncio.sleep(RETRY_DELAY_BASE * (2 ** attempt))
                continue

            body = resp.content or b""
            block = _classify_block(resp.status_code, body)

            if block is None and resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception as exc:  # noqa: BLE001
                    raise UpstreamShapeError(f"non-JSON 200 from {url}: {exc}") from exc
                if not isinstance(data, dict) or "data" not in data:
                    raise UpstreamShapeError(
                        f"unexpected envelope from {url}: keys={list(data)[:8]}"
                    )
                return data

            if block == "cloudflare":
                last_detail = f"cloudflare block (status {resp.status_code})"
                logger.warning("%s on %s -> re-bootstrapping clearance.", last_detail, url)
                await self.waf.ensure_clearance(force=True)
                # rebuild the session so the new UA/TLS/cookies apply cleanly
                await self._reset_session()
                session = await self._ensure_session()
                continue

            if block == "aws":
                last_detail = f"aws block (status {resp.status_code})"
                logger.warning("%s on %s -> re-minting token.", last_detail, url)
                await self.waf.ensure_aws_token(force=True)
                await asyncio.sleep(RETRY_DELAY_BASE * attempt)
                continue

            # Non-block non-200 (e.g. 400 bad params, 404, 5xx) -> surface/backoff
            if resp.status_code in (400, 404):
                raise UpstreamShapeError(
                    f"HTTP {resp.status_code} from {url}: {body[:200]!r}"
                )
            last_detail = f"HTTP {resp.status_code}: {body[:120]!r}"
            await asyncio.sleep(RETRY_DELAY_BASE * (2 ** attempt))

        raise BlockedError(f"Exhausted retries for {url}: {last_detail}")

    async def _reset_session(self) -> None:
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:  # noqa: BLE001
                pass
            self._session = None

    async def close(self) -> None:
        await self._reset_session()
