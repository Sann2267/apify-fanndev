import asyncio

from apify import Actor
from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from src.client import FetchFailed, HandshakeFailed, fetch_list_page, handshake
from src.constants import LIST_PAGE_DELAY, MAX_LIST_PAGES_SAFETY_CAP, PAGE_SIZE, TLS_PROFILE
from src.extractor import build_error_record, build_list_record
from src.input_errors import input_error


async def run_list(
    tipo: str,
    max_results: int,
    entidad: str,
    objeto_contrato: str,
    solo_vigentes: bool,
    tipos_contratacion: tuple[str, ...],
    proxy_url_fn,
) -> list[dict]:
    records: list[dict] = []
    proxy_url = await proxy_url_fn()
    session = AsyncSession(
        impersonate=TLS_PROFILE,
        proxies={"http": proxy_url, "https": proxy_url} if proxy_url else None,
    )
    try:
        try:
            form_token, session_cols = await handshake(session, tipo)
        except (HandshakeFailed, FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
            # NOTE: curl_cffi's own ConnectionError does not inherit from the
            # builtin one (parallel MRO, same name) -- both listed, per the
            # portfolio-wide Babak 22b fix.
            records.append(build_error_record(f"list:tipo={tipo}", "handshake_failed", repr(e)))
            return records

        start = 0
        pages_fetched = 0
        while len(records) < max_results and pages_fetched < MAX_LIST_PAGES_SAFETY_CAP:
            try:
                result = await fetch_list_page(
                    session,
                    form_token,
                    tipo,
                    start,
                    entidad=entidad,
                    objeto_contrato=objeto_contrato,
                    solo_vigentes=solo_vigentes,
                    tipos_contratacion=tipos_contratacion,
                )
            except (FetchFailed, RuntimeError, ConnectionError, RequestException) as e:
                records.append(
                    build_error_record(f"list:tipo={tipo}:start={start}", "blocked_or_transient", repr(e))
                )
                break

            pages_fetched += 1
            rows = result.get("data") if isinstance(result, dict) else None
            if not rows:
                Actor.log.info(f"list: no more rows at start={start} -- reached the end of the result set.")
                break

            for row in rows:
                rec = build_list_record(row, session_cols, tipo)  # raises UnexpectedShape -- not swallowed
                records.append(rec)
                if len(records) >= max_results:
                    break

            records_total = result.get("recordsTotal") if isinstance(result, dict) else None
            start += PAGE_SIZE
            if isinstance(records_total, int) and start >= records_total:
                Actor.log.info(f"list: reached upstream's recordsTotal ({records_total}).")
                break

            if len(records) < max_results:
                await asyncio.sleep(LIST_PAGE_DELAY)

        if pages_fetched >= MAX_LIST_PAGES_SAFETY_CAP:
            Actor.log.info(f"list: hit the {MAX_LIST_PAGES_SAFETY_CAP}-page safety cap with {len(records)} record(s).")
    finally:
        await session.close()

    return records


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        tipo = input_data.get("tipo", "convNacional")
        if tipo not in ("convNacional", "convInternacional"):
            raise input_error(f"tipo must be 'convNacional' or 'convInternacional', got {tipo!r}")

        entidad = str(input_data.get("entidad") or "").strip()
        objeto_contrato = str(input_data.get("objetoContrato") or "").strip()
        solo_vigentes = bool(input_data.get("soloVigentes", True))

        tipos_contratacion_input = input_data.get("tiposContratacion") or ["B", "O", "S", "C"]
        tipos_contratacion = tuple(c for c in tipos_contratacion_input if c in ("B", "O", "S", "C"))
        if not tipos_contratacion:
            tipos_contratacion = ("B", "O", "S", "C")

        max_results = int(input_data.get("maxResults", 50))
        max_results = max(1, min(max_results, 5000))

        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        async def proxy_url_fn():
            return await proxy_config.new_url() if proxy_config else None

        Actor.log.info(
            f"tipo={tipo} entidad={entidad!r} objetoContrato={objeto_contrato!r} "
            f"soloVigentes={solo_vigentes} tiposContratacion={tipos_contratacion} maxResults={max_results}"
        )

        records = await run_list(
            tipo, max_results, entidad, objeto_contrato, solo_vigentes, tipos_contratacion, proxy_url_fn
        )  # UnexpectedShape from build_list_record is intentionally not swallowed

        await Actor.push_data(records)


if __name__ == "__main__":
    asyncio.run(main())
