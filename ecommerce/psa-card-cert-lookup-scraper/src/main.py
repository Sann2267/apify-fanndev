"""Mode dispatch for the PSA cert lookup Actor."""

import asyncio
import logging
import re

from apify import Actor

from src.client import CertNotFound, ChallengedUpstream, PSAClient
from src.constants import MAX_RANGE, MODES, URL_CERT
from src.extractor import (
    extract_error,
    parse_cert_page,
    wrap_cert,
    wrap_reference,
    wrap_sale,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

TRANSIENT = (ChallengedUpstream, RuntimeError, ConnectionError)

_CERT_RE = re.compile(r"\d{5,12}")


def normalize_cert(raw: str) -> str:
    """Accepts '49204884', '#49204884' or a psacard.com/cert/... URL."""
    value = (raw or "").strip()
    if "psacard.com" in value:
        m = re.search(r"/cert/(\d+)", value)
        return m.group(1) if m else ""
    value = value.lstrip("#").strip()
    m = _CERT_RE.fullmatch(value)
    return m.group(0) if m else ""


async def fetch_cert(client: PSAClient, cert: str) -> dict:
    html = await client.get_html(URL_CERT.format(cert=cert))
    parsed = parse_cert_page(cert, html)
    if not parsed["mapped"].get("certNumber") and not parsed["mapped"].get("itemGrade"):
        # A 200 with no item fields means the page shape changed -- louder than
        # returning an empty record that looks like a real but blank cert.
        raise ValueError(
            f"cert {cert} returned a page with no item information "
            f"({len(html)} bytes). The page layout may have changed."
        )
    return parsed


async def run_certs(
    mode: str,
    certs: list[str],
    max_items: int,
    max_concurrency: int,
    proxy_url_factory,
    push,
) -> int:
    sem = asyncio.Semaphore(max_concurrency)
    pushed = 0
    lock = asyncio.Lock()

    async def one(raw: str):
        nonlocal pushed
        cert = normalize_cert(raw)
        if not cert:
            await push([extract_error(raw, "invalid_cert", "expected a numeric PSA certification number")])
            return
        async with sem:
            client = PSAClient(proxy_url=await proxy_url_factory())
            try:
                parsed = await fetch_cert(client, cert)
                if mode == "cert":
                    records = [wrap_cert(cert, parsed, client.profile)]
                else:
                    records = [wrap_sale(cert, i, sale, parsed) for i, sale in enumerate(parsed["sales"])]
                    if not records:
                        records = [
                            extract_error(
                                cert,
                                "empty_section",
                                f"cert {cert} is valid but PSA lists no comparable sales for it",
                            )
                        ]
            except CertNotFound:
                records = [extract_error(cert, "not_found", "PSA has no such certification number")]
            except ValueError as e:
                records = [extract_error(cert, "shape_changed", str(e))]
            except TRANSIENT as e:
                records = [extract_error(cert, "blocked_or_transient", repr(e))]
            finally:
                await client.close()

            async with lock:
                room = max_items - pushed
                if room <= 0:
                    return
                records = records[:room]
                pushed += len(records)
            await push(records)

    await asyncio.gather(*(one(c) for c in certs))
    return pushed


async def run_reference(proxy_url: str | None) -> list[dict]:
    """Probe the public surface and report which TLS profile got through --
    the single fact that decides whether this Actor works at all today."""
    client = PSAClient(proxy_url=proxy_url)
    url = URL_CERT.format(cert="49204884")
    try:
        parsed = await fetch_cert(client, "49204884")
        sample = {
            "certNumber": parsed["mapped"].get("certNumber"),
            "subject": parsed["mapped"].get("subject"),
            "itemGrade": parsed["mapped"].get("itemGrade"),
            "psaEstimate": parsed.get("estimate"),
            "psaPopulation": parsed.get("population"),
            "recentSales": len(parsed["sales"]),
            "tlsProfile": client.profile,
        }
        return [wrap_reference("cert-page", url, True, "payload parsed", sample)]
    except (ChallengedUpstream, CertNotFound, ValueError) as e:
        return [wrap_reference("cert-page", url, False, repr(e), {"triedProfiles": list(client.profiles)})]
    finally:
        await client.close()


def _clean_certs(input_data: dict) -> list[str]:
    values = list(input_data.get("certNumbers") or [])
    if input_data.get("certNumber"):
        values.insert(0, input_data["certNumber"])
    out: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in out:
            out.append(text)
    return out


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "cert")
        if mode not in MODES:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {MODES}.")

        max_items = int(input_data.get("maxItems", 200))
        max_concurrency = int(input_data.get("maxConcurrency", 3))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def new_proxy_url():
            return await proxy_config.new_url() if proxy_config else None

        async def push(records: list[dict]):
            if records:
                await Actor.push_data(records)

        if mode == "reference":
            records = await run_reference(await new_proxy_url())
            Actor.log.info(f"mode=reference: available={records[0].get('isAvailable')}")
            await push(records)
            return

        if mode == "range":
            start = normalize_cert(str(input_data.get("startCert") or ""))
            if not start:
                raise input_error("Provide 'startCert' (a numeric certification number) for mode 'range'.")
            count = int(input_data.get("rangeCount", 25))
            if count < 1 or count > MAX_RANGE:
                raise input_error(f"'rangeCount' must be between 1 and {MAX_RANGE}.")
            certs = [str(int(start) + i) for i in range(count)]
            Actor.log.info(f"mode=range: {certs[0]}..{certs[-1]} ({count} certs)")
            count = await run_certs("cert", certs, max_items, max_concurrency, new_proxy_url, push)
            Actor.log.info(f"mode=range -> {count} record(s)")
            return

        certs = _clean_certs(input_data)
        if not certs:
            raise input_error(f"Provide 'certNumber' or 'certNumbers' for mode '{mode}'.")

        count = await run_certs(mode, certs, max_items, max_concurrency, new_proxy_url, push)
        Actor.log.info(f"mode={mode} certs={len(certs)} -> {count} record(s)")
