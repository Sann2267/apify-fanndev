"""Facebook Ads Performance Calculator & Benchmarker -- Apify actor entry point."""

from __future__ import annotations

from apify import Actor

from src.analytics import benchmark, compare
from src.exporters import BUILDERS
from src.fbcore import BlockedError, FacebookSession
from src.parser import summarise
from src.runtime import envelope, error_record, resolve_proxy, write_exports
from src.search import collect, page_id_from
from src.input_errors import input_error

SOURCE = "ad-library-benchmark"

# Metrics worth comparing across niches when more than one was run.
COMPARED_METRICS = ["TOP_CTA", "TOP_FORMAT", "TOP_WORD", "TOP_PHRASE_2"]


def read_niches(actor_input: dict) -> list[dict]:
    """A niche is a label plus the searches that fill its sample.

    Two input shapes are accepted. The simple one treats each keyword as its own
    niche; the grouped one lets several keywords and advertisers feed a single
    benchmark, which is what you want when "skincare" means eight brands rather
    than one word.
    """
    niches: list[dict] = []

    for term in actor_input.get("niches") or []:
        if isinstance(term, dict):
            label = (term.get("name") or term.get("label") or "").strip()
            terms = [str(t).strip() for t in (term.get("keywords") or []) if str(t).strip()]
            advertisers = [
                page_id_from(str(a)) for a in (term.get("advertisers") or [])
            ]
            advertisers = [a for a in advertisers if a]
            if not label:
                label = terms[0] if terms else (advertisers[0] if advertisers else "")
            if label and (terms or advertisers):
                niches.append({"name": label, "keywords": terms, "advertisers": advertisers})
        else:
            label = str(term).strip()
            if label:
                niches.append({"name": label, "keywords": [label], "advertisers": []})

    return niches


def build_queries(niche: dict, actor_input: dict, countries: list[str]) -> list[dict]:
    common = {
        "activeStatus": actor_input.get("activeStatus") or "active",
        "adType": actor_input.get("adType") or "all",
        "mediaType": actor_input.get("mediaType") or "all",
        "searchType": actor_input.get("searchType") or "keyword_unordered",
        "publisherPlatforms": actor_input.get("publisherPlatforms") or [],
        "contentLanguages": actor_input.get("contentLanguages") or [],
        "startDateMin": None,
        "startDateMax": None,
    }
    queries = []
    for country in countries:
        for keyword in niche["keywords"]:
            queries.append({**common, "country": country, "term": keyword, "pageId": None,
                            "label": f"{niche['name']} / keyword:{keyword} @ {country}"})
        for page_id in niche["advertisers"]:
            queries.append({**common, "country": country, "term": None, "pageId": page_id,
                            "label": f"{niche['name']} / page:{page_id} @ {country}"})
    return queries


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        niches = read_niches(actor_input)
        if not niches:
            raise input_error(
                "Nothing to benchmark. Supply niches as a list of keywords "
                '(["skincare", "protein powder"]) or as groups '
                '([{"name": "skincare", "keywords": ["serum", "moisturiser"]}]).'
            )

        countries = [c.strip().upper() for c in (actor_input.get("countries") or ["US"])
                     if str(c).strip()]
        countries = list(dict.fromkeys(countries)) or ["US"]

        sample_size = max(30, min(int(actor_input.get("sampleSizePerNiche", 150)), 2000))
        settings = {
            "topN": max(3, min(int(actor_input.get("topN", 10)), 50)),
            "minGroupSample": max(1, min(int(actor_input.get("minGroupSample", 3)), 50)),
        }
        include_ads = bool(actor_input.get("includeAdSample"))
        export_formats = actor_input.get("exportFormats") or []
        proxy_url = await resolve_proxy(actor_input)

        # The benchmark is about what a niche is running, so the sample is not
        # filtered down before it is measured -- filtering first would benchmark
        # the filter.
        filters = {"onlyActive": False, "onlyWithVideo": False,
                   "minRunningDays": None, "adTextContains": None}

        Actor.log.info(
            f"Benchmarking {len(niches)} niche(s) across {len(countries)} country/countries, "
            f"up to {sample_size} ad(s) per niche."
        )

        records: list[dict] = []
        all_benchmarks: list[dict] = []
        failures = 0
        samples: dict[str, int] = {}

        async with FacebookSession(proxy_url=proxy_url, log=Actor.log) as session:
            for niche in niches:
                queries = build_queries(niche, actor_input, countries)
                # The sample budget is shared across the searches that feed the
                # niche, so a two-keyword niche does not silently collect twice
                # the ads of a one-keyword niche and look twice as confident.
                per_query = max(30, sample_size // max(1, len(queries)))
                ads: list[dict] = []
                seen: set[str] = set()

                for query in queries:
                    try:
                        found, meta = await collect(session, query, per_query, filters)
                    except BlockedError as exc:
                        failures += 1
                        record = error_record(SOURCE, query["label"], "fetch_failed", str(exc))
                        records.append(record)
                        await Actor.push_data(record)
                        continue
                    except Exception as exc:
                        failures += 1
                        record = error_record(
                            SOURCE, query["label"], "unexpected_error",
                            f"{type(exc).__name__}: {exc}",
                        )
                        records.append(record)
                        await Actor.push_data(record)
                        continue

                    for ad in found:
                        key = ad.get("adArchiveId")
                        if key and key not in seen:
                            seen.add(key)
                            ads.append(ad)
                    Actor.log.info(f"{query['label']}: +{len(found)} ad(s)")

                samples[niche["name"]] = len(ads)
                if not ads:
                    Actor.log.warning(
                        f"{niche['name']}: no ads found -- nothing to benchmark. "
                        "Try a broader keyword, another country, or activeStatus=all."
                    )
                    continue

                for row in benchmark(niche["name"], ads, settings):
                    record = {**envelope(SOURCE, niche["name"], "BENCHMARK"), **row}
                    records.append(record)
                    all_benchmarks.append(record)
                    await Actor.push_data(record)

                if include_ads:
                    for ad in ads:
                        record = {**envelope(SOURCE, niche["name"], "AD_SAMPLE"),
                                  "niche": niche["name"], **ad}
                        records.append(record)
                        await Actor.push_data(record)

        if len(niches) > 1 and all_benchmarks:
            for metric in COMPARED_METRICS:
                for row in compare(all_benchmarks, metric, settings["topN"]):
                    record = {**envelope(SOURCE, "all niches", "COMPARISON"), **row}
                    records.append(record)
                    await Actor.push_data(record)

        summary = {
            **envelope(SOURCE, f"{len(niches)} niche(s)", "RUN_SUMMARY"),
            "nichesBenchmarked": sum(1 for n in niches if samples.get(n["name"])),
            "nichesRequested": len(niches),
            "adsSampled": sum(samples.values()),
            "sampleSizePerNiche": samples,
            "benchmarkRows": len(all_benchmarks),
            "failedSearches": failures,
        }
        records.append(summary)
        await Actor.push_data(summary)
        Actor.log.info(
            f"Finished: {summary['adsSampled']} ad(s) sampled, "
            f"{summary['benchmarkRows']} benchmark row(s), {failures} failed search(es)"
        )

        await write_exports(records, export_formats, BUILDERS)

        if failures and not all_benchmarks:
            raise RuntimeError(
                "Every search failed and no benchmark could be computed -- "
                "see the ERROR records."
            )


__all__ = ["main", "summarise"]
