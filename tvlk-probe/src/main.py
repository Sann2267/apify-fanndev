"""Throwaway probe: how often does Traveloka's AWS WAF answer `captcha` to the
session bootstrap (`POST /api/v2/user/context/web`) per Apify proxy group?

Each proxy group gets N fresh sessions (one new exit IP each); every outcome is
pushed to the dataset so the captcha rate per group can be read off directly.
"""

from __future__ import annotations

import asyncio
import uuid

from apify import Actor
from curl_cffi import requests

SITE = "https://www.traveloka.com"
API = SITE + "/api/v2/user/context/web"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
PAYLOAD = {
    "clientInterface": "desktop",
    "data": {"client": "MOBILE_WEB", "info": {"User-Agent": UA}, "query": {}},
    "context": {},
    "fields": [],
}
GROUPS = {
    "auto": {"useApifyProxy": True},
    "residential": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]},
    "residential-ID": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"],
                       "apifyProxyCountry": "ID"},
    "residential-SG": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"],
                       "apifyProxyCountry": "SG"},
    "residential-US": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"],
                       "apifyProxyCountry": "US"},
}


def probe(proxy_url: str, profile: str) -> dict:
    s = requests.Session(impersonate=profile, proxies={"http": proxy_url, "https": proxy_url})
    try:
        ip = s.get("https://api.ipify.org", timeout=20).text.strip()
    except Exception as exc:  # noqa: BLE001
        ip = f"err {exc}"[:60]
    try:
        r = s.post(API, json=PAYLOAD, timeout=30, headers={
            "user-agent": UA, "content-type": "application/json", "origin": SITE,
            "referer": SITE + "/en-id/", "x-domain": "user", "x-client-interface": "desktop"})
        return {"ip": ip, "status": r.status_code, "waf": r.headers.get("x-amzn-waf-action"),
                "cookies": sorted(s.cookies.keys())}
    except Exception as exc:  # noqa: BLE001
        return {"ip": ip, "status": None, "waf": None, "error": str(exc)[:160]}


async def main() -> None:
    async with Actor:
        inp = await Actor.get_input() or {}
        n = int(inp.get("perGroup") or 15)
        groups = inp.get("groups") or list(GROUPS)
        for name in groups:
            try:
                conf = await Actor.create_proxy_configuration(actor_proxy_input=GROUPS[name])
            except Exception as exc:  # noqa: BLE001
                Actor.log.warning("%s: no proxy configuration (%s)", name, exc)
                continue
            ok = 0
            for i in range(n):
                url = await conf.new_url(uuid.uuid4().hex[:10])
                profile = ["chrome131", "chrome124", "safari17_0", "edge101", "chrome120"][i % 5]
                res = await asyncio.to_thread(probe, url, profile)
                res.update(group=name, profile=profile)
                ok += res["status"] == 200
                await Actor.push_data(res)
            Actor.log.info("GROUP %s: %d/%d bootstrap OK", name, ok, n)
