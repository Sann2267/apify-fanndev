import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import AlodokterClient, NotFound
from src.constants import (
    MODES,
    PATH_SPECIALTY,
    PATH_SPECIALTY_CITY,
    SPECIALTIES,
)
from src.extractor import (
    absolute,
    city_slugs,
    extract_error,
    parse_listing,
    parse_profile,
    profile_path_from_input,
    wrap,
)
from src.input_errors import input_error

log = logging.getLogger(__name__)

TRANSIENT = (RuntimeError, ConnectionError, RequestException)


async def run_specialty(
    specialty: str, city: str | None, max_items: int, proxy_url: str | None
) -> list[dict]:
    specialty = specialty.strip().strip("/").lower()
    label = f"specialty:{specialty}" + (f"/{city}" if city else "")
    path = (
        PATH_SPECIALTY_CITY.format(specialty=specialty, city=city.strip().lower())
        if city
        else PATH_SPECIALTY.format(specialty=specialty)
    )

    client = AlodokterClient(proxy_url=proxy_url)
    try:
        doctors = await client.paginate(path, max_items, parse_listing)
        records = []
        for d in doctors:
            rec = wrap(d, label, record_type="DOCTOR_CARD")
            rec["_listingScope"] = label
            records.append(rec)
        return records
    except NotFound as e:
        return [
            extract_error(
                label,
                "not_found",
                f"{e} -- run mode=reference for valid specialty/city slugs",
            )
        ]
    except TRANSIENT as e:
        return [extract_error(label, "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def run_doctor(raw_input: str, proxy_url: str | None) -> dict:
    path = profile_path_from_input(raw_input)
    if not path:
        return extract_error(raw_input, "empty_input")

    client = AlodokterClient(proxy_url=proxy_url)
    try:
        html = await client.get_html(path)
        data = parse_profile(html, absolute(path))
        if not data.get("name"):
            return extract_error(raw_input, "not_a_profile", f"no doctor record parsed from {path}")
        return wrap(data, raw_input, record_type="DOCTOR_PROFILE")
    except NotFound:
        return extract_error(raw_input, "not_found", path)
    except TRANSIENT as e:
        return extract_error(raw_input, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def run_reference(proxy_url: str | None) -> list[dict]:
    """Verify each known specialty slug live and emit the city facets that
    the largest one links. Specialty slugs are checked rather than trusted
    because an unknown slug answers 200 with a soft-404 shell."""
    client = AlodokterClient(proxy_url=proxy_url)
    try:
        records = []
        first_html = None
        for slug in SPECIALTIES:
            try:
                html = await client.get_html(
                    PATH_SPECIALTY.format(specialty=slug), check_soft_404=True
                )
            except NotFound:
                continue
            doctors = parse_listing(html)
            if first_html is None and doctors:
                first_html = (slug, html)
            records.append(
                wrap(
                    {
                        "slug": slug,
                        "listingUrl": absolute(PATH_SPECIALTY.format(specialty=slug)),
                        "doctorsOnFirstPage": len(doctors),
                        "listName": doctors[0].get("listName") if doctors else None,
                    },
                    "reference",
                    record_type="SPECIALTY",
                )
            )
        if first_html:
            slug, html = first_html
            for city in city_slugs(html, slug):
                records.append(
                    wrap(
                        {
                            "slug": city,
                            "listingUrl": absolute(
                                PATH_SPECIALTY_CITY.format(specialty=slug, city=city)
                            ),
                        },
                        "reference",
                        record_type="CITY",
                    )
                )
        return records
    except TRANSIENT as e:
        return [extract_error("reference", "blocked_or_transient", repr(e))]
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "specialty")
        if mode not in MODES:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {MODES}.")

        max_items = int(input_data.get("maxItems", 100))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def new_proxy_url():
            return await proxy_config.new_url() if proxy_config else None

        if mode == "reference":
            records = await run_reference(await new_proxy_url())
            Actor.log.info(f"mode=reference: {len(records)} record(s)")
            await Actor.push_data(records)
            return

        if mode == "specialty":
            specialties = list(input_data.get("specialties") or [])
            if input_data.get("specialty"):
                specialties.insert(0, input_data["specialty"])
            if not specialties:
                raise input_error("Provide 'specialty' or 'specialties' when mode is 'specialty'.")
            seen = set()
            specialties = [s for s in specialties if not (s in seen or seen.add(s))]
            city = (input_data.get("city") or "").strip() or None

            all_records = []
            for s in specialties:
                records = await run_specialty(s, city, max_items, await new_proxy_url())
                Actor.log.info(f"  {s} city={city!r}: {len(records)} record(s)")
                await Actor.push_data(records)
                all_records.extend(records)

            if input_data.get("enrichProfiles"):
                urls = [r["profileUrl"] for r in all_records if r.get("profileUrl")]
                Actor.log.info(f"enrichProfiles: fetching {len(urls)} profile(s)")
                await _fetch_doctors(urls, int(input_data.get("maxConcurrency", 4)), new_proxy_url)
            return

        # mode == "doctor"
        urls = list(input_data.get("doctorUrls") or [])
        if input_data.get("doctorUrl"):
            urls.insert(0, input_data["doctorUrl"])
        if not urls:
            raise input_error("Provide 'doctorUrl' or 'doctorUrls' when mode is 'doctor'.")
        seen = set()
        urls = [u for u in urls if not (u in seen or seen.add(u))]

        Actor.log.info(f"mode=doctor: {len(urls)} profile(s)")
        await _fetch_doctors(urls, int(input_data.get("maxConcurrency", 4)), new_proxy_url)


async def _fetch_doctors(urls: list[str], max_concurrency: int, new_proxy_url) -> None:
    sem = asyncio.Semaphore(max_concurrency)

    async def _bounded(u: str):
        async with sem:
            record = await run_doctor(u, await new_proxy_url())
            await Actor.push_data(record)

    await asyncio.gather(*(_bounded(u) for u in urls))
