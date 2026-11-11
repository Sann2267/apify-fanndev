"""WAF session management: AWS WAF token minting (headless Node) + Cloudflare
`cf_clearance` bootstrap (Camoufox), plus the resulting identity (cookies + UA)
that the HTTP client replays.

Two independent gates protect the API:

* **AWS WAF** — every `/api/get/` route needs an `x-aws-waf-token`. We mint it
  with a Node/jsdom subprocess (`mint_token.js`); no browser, ~2-3s, refreshable.
* **Cloudflare managed challenge** — only `search/result` needs a `cf_clearance`
  cookie, which requires a real browser. Camoufox earns it once; the cookie is
  IP+UA-bound but replayable over curl_cffi with a matching Firefox profile.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from src.constants import AWS_SDK_URL, AWS_TOKEN_TTL, SITE

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
_MINT_SCRIPT = os.path.join(_HERE, "mint_token.js")


class WafError(RuntimeError):
    """Raised when a WAF gate cannot be satisfied."""


@dataclass
class WafIdentity:
    """Everything the HTTP client needs to look like the browser that passed."""

    aws_token: str = ""
    aws_token_ts: float = 0.0
    cf_clearance: str = ""
    aws_cookie: str = ""
    user_agent: str = ""
    extra_cookies: dict[str, str] = field(default_factory=dict)

    def aws_token_fresh(self) -> bool:
        return bool(self.aws_token) and (time.time() - self.aws_token_ts) < AWS_TOKEN_TTL

    def has_clearance(self) -> bool:
        return bool(self.cf_clearance)


async def mint_aws_token(sdk_url: str = AWS_SDK_URL) -> str:
    """Run the Node minter and return a fresh `x-aws-waf-token`."""
    proc = await asyncio.create_subprocess_exec(
        "node",
        _MINT_SCRIPT,
        sdk_url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=60)
    except asyncio.TimeoutError as exc:
        proc.kill()
        raise WafError("AWS token mint timed out") from exc
    token = (out or b"").decode().strip()
    if proc.returncode != 0 or not token:
        detail = (err or b"").decode()[:300]
        raise WafError(f"AWS token mint failed (rc={proc.returncode}): {detail}")
    logger.info("Minted AWS WAF token (len=%d).", len(token))
    return token


async def bootstrap_clearance(proxy_url: str | None = None) -> dict:
    """Launch Camoufox, earn `cf_clearance` for search/result, harvest cookies+UA.

    Returns a dict with cf_clearance, aws_cookie, user_agent, extra_cookies.
    Imported lazily so non-search runs never pay the Camoufox import/launch cost.
    """
    from camoufox.async_api import AsyncCamoufox

    launch_kwargs: dict = {"headless": True, "humanize": True}
    if proxy_url:
        # Firefox/Playwright rejects credentials embedded in the server URL;
        # split them into the {server, username, password} shape it expects.
        parts = urlsplit(proxy_url)
        server = f"{parts.scheme}://{parts.hostname}"
        if parts.port:
            server += f":{parts.port}"
        proxy_cfg: dict = {"server": server}
        if parts.username:
            proxy_cfg["username"] = parts.username
        if parts.password:
            proxy_cfg["password"] = parts.password
        launch_kwargs["proxy"] = proxy_cfg
        # geoip lets Camoufox align timezone/locale with the proxy exit IP.
        launch_kwargs["geoip"] = True

    logger.info("Bootstrapping Cloudflare clearance via Camoufox%s...",
                " (proxied)" if proxy_url else "")
    async with AsyncCamoufox(**launch_kwargs) as browser:
        page = await browser.new_page()
        await page.goto(SITE + "/", wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(5000)
        # Navigate a search page so Cloudflare issues clearance scoped to the
        # protected /search/result route.
        try:
            await page.goto(
                SITE + "/search?key=indomie",
                wait_until="networkidle",
                timeout=90000,
            )
            await page.wait_for_timeout(5000)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Search-page warmup navigation failed: %s", exc)

        cookies = await page.context.cookies()
        user_agent = await page.evaluate("() => navigator.userAgent")

    by_name = {c["name"]: c["value"] for c in cookies}
    cf = by_name.get("cf_clearance", "")
    aws = by_name.get("aws-waf-token", "")
    if not cf:
        raise WafError("Camoufox did not obtain a cf_clearance cookie.")
    logger.info("Clearance bootstrapped (cf_clearance len=%d, aws cookie=%s).",
                len(cf), "yes" if aws else "no")
    return {
        "cf_clearance": cf,
        "aws_cookie": aws,
        "user_agent": user_agent,
        "extra_cookies": {c["name"]: c["value"] for c in cookies},
    }


class WafManager:
    """Owns the WAF identity and refreshes each gate on demand."""

    def __init__(self, proxy_url: str | None = None) -> None:
        self.identity = WafIdentity()
        self._proxy_url = proxy_url
        self._lock = asyncio.Lock()

    async def ensure_aws_token(self, force: bool = False) -> str:
        async with self._lock:
            if force or not self.identity.aws_token_fresh():
                token = await mint_aws_token()
                self.identity.aws_token = token
                self.identity.aws_token_ts = time.time()
            return self.identity.aws_token

    async def ensure_clearance(self, force: bool = False) -> None:
        async with self._lock:
            if force or not self.identity.has_clearance():
                data = await bootstrap_clearance(self._proxy_url)
                self.identity.cf_clearance = data["cf_clearance"]
                self.identity.aws_cookie = data["aws_cookie"]
                self.identity.user_agent = data["user_agent"]
                self.identity.extra_cookies = data["extra_cookies"]
                # A clearance bootstrap also yields a fresh AWS cookie; prefer it.
                if data["aws_cookie"]:
                    self.identity.aws_token = data["aws_cookie"]
                    self.identity.aws_token_ts = time.time()
