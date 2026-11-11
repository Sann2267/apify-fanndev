import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import CivitaiClient, InvalidRequest, NotFound
from src.constants import (
    BASE_URL,
    IMAGE_NSFW_VALUES,
    IMAGE_SORT_VALUES,
    MODEL_PERIOD_VALUES,
    MODEL_SORT_VALUES,
    MODEL_TYPE_VALUES,
)
from src.extractor import extract_error, wrap
from src.input_errors import input_error

log = logging.getLogger(__name__)


def _validate_enum(input_data: dict, field: str, valid: list[str]):
    value = input_data.get(field)
    if value and value not in valid:
        raise ValueError(f"Invalid {field}: {value!r}. Must be one of {valid}.")


def _validate_enum_list(input_data: dict, field: str, valid: list[str]):
    values = input_data.get(field) or []
    for v in values:
        if v not in valid:
            raise ValueError(f"Invalid entry in {field}: {v!r}. Must be one of {valid}.")


async def run_models_search(input_data: dict, max_items: int, proxy_url: str | None) -> list[dict]:
    params = {}
    if input_data.get("query"):
        params["query"] = input_data["query"]
    if input_data.get("tag"):
        params["tag"] = input_data["tag"]
    if input_data.get("username"):
        params["username"] = input_data["username"]
    if input_data.get("types"):
        params["types"] = input_data["types"]
    if input_data.get("sort"):
        params["sort"] = input_data["sort"]
    if input_data.get("period"):
        params["period"] = input_data["period"]
    if "nsfw" in input_data:
        params["nsfw"] = input_data["nsfw"]

    client = CivitaiClient(proxy_url=proxy_url)
    try:
        items = await client.paginate("/models", params, max_items)
        input_desc = input_data.get("query") or "models-search"
        return [wrap(item, input_desc) for item in items]
    except InvalidRequest as e:
        return [extract_error("models-search", "invalid_request", repr(e))]
    finally:
        await client.close()


async def run_model_detail(model_id: str, proxy_url: str | None) -> dict:
    client = CivitaiClient(proxy_url=proxy_url)
    try:
        data = await client.get_json(f"{BASE_URL}/models/{model_id}")
        return wrap(data, str(model_id))
    except NotFound as e:
        return extract_error(str(model_id), "model_not_found", repr(e))
    except InvalidRequest as e:
        return extract_error(str(model_id), "invalid_request", repr(e))
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(str(model_id), "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def _resolve_model_version_ids(client: CivitaiClient, model_id) -> list[int]:
    """`/images?modelId=X` is confirmed broken upstream -- it returns
    `{"items":[],"metadata":{}}` even for the most popular models on
    civitai.com (see CRAWLING_METHOD.md). Image objects are actually
    tagged by `modelVersionIds`, and `/images?modelVersionId=X` works
    reliably, so a `modelId` input is resolved to its version IDs first."""
    data = await client.get_json(f"{BASE_URL}/models/{model_id}")
    return [v["id"] for v in data.get("modelVersions", []) if v.get("id")]


def _base_image_params(input_data: dict) -> dict:
    params = {}
    if input_data.get("username"):
        params["username"] = input_data["username"]
    if input_data.get("postId"):
        params["postId"] = input_data["postId"]
    if input_data.get("sort"):
        params["sort"] = input_data["sort"]
    if input_data.get("period"):
        params["period"] = input_data["period"]
    if input_data.get("nsfw"):
        params["nsfw"] = input_data["nsfw"]
    return params


async def run_images(input_data: dict, max_items: int, proxy_url: str | None) -> list[dict]:
    client = CivitaiClient(proxy_url=proxy_url)
    try:
        params = _base_image_params(input_data)

        if input_data.get("modelVersionId"):
            params["modelVersionId"] = input_data["modelVersionId"]
            items = await client.paginate("/images", params, max_items)
            input_desc = str(input_data["modelVersionId"])
            return [wrap(item, input_desc) for item in items]

        if input_data.get("modelId"):
            model_id = input_data["modelId"]
            try:
                version_ids = await _resolve_model_version_ids(client, model_id)
            except NotFound as e:
                return [extract_error(str(model_id), "model_not_found", repr(e))]
            items: list[dict] = []
            for vid in version_ids:
                if len(items) >= max_items:
                    break
                version_params = {**params, "modelVersionId": vid}
                items.extend(await client.paginate("/images", version_params, max_items - len(items)))
            return [wrap(item, str(model_id)) for item in items[:max_items]]

        items = await client.paginate("/images", params, max_items)
        input_desc = str(input_data.get("username") or "images-search")
        return [wrap(item, input_desc) for item in items]
    except InvalidRequest as e:
        return [extract_error("images-search", "invalid_request", repr(e))]
    finally:
        await client.close()


async def run_creators(input_data: dict, max_items: int, proxy_url: str | None) -> list[dict]:
    params = {}
    if input_data.get("query"):
        params["query"] = input_data["query"]

    client = CivitaiClient(proxy_url=proxy_url)
    try:
        items = await client.paginate("/creators", params, max_items)
        input_desc = input_data.get("query") or "creators-list"
        return [wrap(item, input_desc) for item in items]
    except InvalidRequest as e:
        return [extract_error("creators-list", "invalid_request", repr(e))]
    finally:
        await client.close()


async def run_tags(input_data: dict, max_items: int, proxy_url: str | None) -> list[dict]:
    params = {}
    if input_data.get("query"):
        params["query"] = input_data["query"]

    client = CivitaiClient(proxy_url=proxy_url)
    try:
        items = await client.paginate("/tags", params, max_items)
        input_desc = input_data.get("query") or "tags-list"
        return [wrap(item, input_desc) for item in items]
    except InvalidRequest as e:
        return [extract_error("tags-list", "invalid_request", repr(e))]
    finally:
        await client.close()


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "models")
        if mode not in ("models", "model-detail", "images", "creators", "tags"):
            raise input_error(f"Invalid mode: {mode!r}. Must be one of models/model-detail/images/creators/tags.")

        _validate_enum(input_data, "sort", MODEL_SORT_VALUES if mode == "models" else IMAGE_SORT_VALUES)
        _validate_enum(input_data, "period", MODEL_PERIOD_VALUES)
        _validate_enum_list(input_data, "types", MODEL_TYPE_VALUES)
        if mode == "images" and input_data.get("nsfw") not in (None, *IMAGE_NSFW_VALUES):
            raise input_error(f"Invalid nsfw: {input_data['nsfw']!r}. Must be one of {IMAGE_NSFW_VALUES}.")

        max_items = int(input_data.get("maxItems", 100))
        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        if mode == "model-detail":
            model_ids = [str(i) for i in (input_data.get("modelIds") or [])]
            if input_data.get("modelId"):
                model_ids.insert(0, str(input_data["modelId"]))
            if not model_ids:
                raise input_error("Provide 'modelId' or 'modelIds' when mode is 'model-detail'.")
            seen = set()
            model_ids = [m for m in model_ids if not (m in seen or seen.add(m))]

            max_concurrency = int(input_data.get("maxConcurrency", 4))
            sem = asyncio.Semaphore(max_concurrency)

            async def _bounded(model_id: str):
                async with sem:
                    proxy_url = await proxy_config.new_url() if proxy_config else None
                    record = await run_model_detail(model_id, proxy_url)
                    await Actor.push_data(record)

            Actor.log.info(f"mode=model-detail: {len(model_ids)} model(s), maxConcurrency={max_concurrency}")
            await asyncio.gather(*(_bounded(m) for m in model_ids))
            return

        proxy_url = await proxy_config.new_url() if proxy_config else None
        if mode == "models":
            records = await run_models_search(input_data, max_items, proxy_url)
        elif mode == "images":
            records = await run_images(input_data, max_items, proxy_url)
        elif mode == "creators":
            records = await run_creators(input_data, max_items, proxy_url)
        else:  # tags
            records = await run_tags(input_data, max_items, proxy_url)

        Actor.log.info(f"mode={mode}: {len(records)} record(s), maxItems={max_items}")
        await Actor.push_data(records)
