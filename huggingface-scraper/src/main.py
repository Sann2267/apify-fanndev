import asyncio
import logging

from apify import Actor
from curl_cffi.requests.exceptions import RequestException

from src.client import HuggingFaceClient, InvalidRequest, NotFound
from src.constants import BASE_URL, DIRECTION_VALUES, SORT_VALUES
from src.extractor import extract_error, wrap
from src.input_errors import input_error

log = logging.getLogger(__name__)


def _validate_enum(input_data: dict, field: str, valid: list):
    value = input_data.get(field)
    if value is not None and value not in valid:
        raise ValueError(f"Invalid {field}: {value!r}. Must be one of {valid}.")


def _search_params(input_data: dict, extra_field_map: dict[str, str] | None = None) -> dict:
    params = {}
    if input_data.get("search"):
        params["search"] = input_data["search"]
    if input_data.get("author"):
        params["author"] = input_data["author"]
    if input_data.get("filter"):
        params["filter"] = input_data["filter"]
    if input_data.get("sort"):
        params["sort"] = input_data["sort"]
    if "direction" in input_data and input_data["direction"] is not None:
        params["direction"] = input_data["direction"]
    for input_field, upstream_param in (extra_field_map or {}).items():
        if input_data.get(input_field):
            params[upstream_param] = input_data[input_field]
    return params


async def run_list(entity: str, input_data: dict, max_items: int, proxy_url: str | None) -> list[dict]:
    extra = {"pipelineTag": "pipeline_tag", "library": "library"} if entity == "models" else None
    params = _search_params(input_data, extra)

    client = HuggingFaceClient(proxy_url=proxy_url)
    try:
        items = await client.paginate(f"{BASE_URL}/{entity}", params, max_items)
        input_desc = input_data.get("search") or input_data.get("author") or f"{entity}-list"
        return [wrap(item, input_desc) for item in items]
    except InvalidRequest as e:
        return [extract_error(f"{entity}-list", "invalid_request", repr(e))]
    finally:
        await client.close()


async def run_detail(entity: str, repo_id: str, proxy_url: str | None) -> dict:
    client = HuggingFaceClient(proxy_url=proxy_url)
    try:
        data = await client.get_repo_detail_json(f"{BASE_URL}/{entity}/{repo_id}")
        return wrap(data, repo_id)
    except NotFound as e:
        return extract_error(repo_id, f"{entity[:-1]}_not_found", repr(e))
    except InvalidRequest as e:
        return extract_error(repo_id, "invalid_request", repr(e))
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(repo_id, "blocked_or_transient", repr(e))
    finally:
        await client.close()


async def run_creator(username: str, account_type: str, proxy_url: str | None) -> dict:
    client = HuggingFaceClient(proxy_url=proxy_url)
    try:
        if account_type == "user":
            data = await client.get_repo_json(f"{BASE_URL}/users/{username}/overview")
            return wrap(data, username, "S1-api-user")
        if account_type == "organization":
            data = await client.get_repo_json(f"{BASE_URL}/organizations/{username}/overview")
            return wrap(data, username, "S1-api-organization")

        # auto: try user first, fall back to organization
        try:
            data = await client.get_repo_json(f"{BASE_URL}/users/{username}/overview")
            return wrap(data, username, "S1-api-user")
        except NotFound:
            data = await client.get_repo_json(f"{BASE_URL}/organizations/{username}/overview")
            return wrap(data, username, "S1-api-organization")
    except NotFound as e:
        return extract_error(username, "creator_not_found", repr(e))
    except InvalidRequest as e:
        return extract_error(username, "invalid_request", repr(e))
    except (RuntimeError, ConnectionError, RequestException) as e:
        return extract_error(username, "blocked_or_transient", repr(e))
    finally:
        await client.close()


DETAIL_ENTITY_BY_MODE = {
    "model-detail": "models",
    "dataset-detail": "datasets",
    "space-detail": "spaces",
}
LIST_ENTITY_BY_MODE = {
    "models": "models",
    "datasets": "datasets",
    "spaces": "spaces",
}
ID_FIELD_BY_MODE = {
    "model-detail": ("modelId", "modelIds"),
    "dataset-detail": ("datasetId", "datasetIds"),
    "space-detail": ("spaceId", "spaceIds"),
}


async def main():
    async with Actor:
        input_data = await Actor.get_input() or {}

        mode = input_data.get("mode", "models")
        valid_modes = ("models", "model-detail", "datasets", "dataset-detail", "spaces", "space-detail", "creator")
        if mode not in valid_modes:
            raise input_error(f"Invalid mode: {mode!r}. Must be one of {valid_modes}.")

        _validate_enum(input_data, "sort", SORT_VALUES)
        _validate_enum(input_data, "direction", DIRECTION_VALUES)
        _validate_enum(input_data, "accountType", ["auto", "user", "organization"])

        max_items = int(input_data.get("maxItems", 100))
        proxy_config = await Actor.create_proxy_configuration(
            actor_proxy_input=input_data.get("proxyConfiguration"),
        )

        if mode in DETAIL_ENTITY_BY_MODE:
            entity = DETAIL_ENTITY_BY_MODE[mode]
            single_field, list_field = ID_FIELD_BY_MODE[mode]
            repo_ids = [str(i) for i in (input_data.get(list_field) or [])]
            if input_data.get(single_field):
                repo_ids.insert(0, str(input_data[single_field]))
            if not repo_ids:
                raise input_error(f"Provide '{single_field}' or '{list_field}' when mode is {mode!r}.")
            seen = set()
            repo_ids = [r for r in repo_ids if not (r in seen or seen.add(r))]

            max_concurrency = int(input_data.get("maxConcurrency", 4))
            sem = asyncio.Semaphore(max_concurrency)

            async def _bounded(repo_id: str):
                async with sem:
                    proxy_url = await proxy_config.new_url() if proxy_config else None
                    record = await run_detail(entity, repo_id, proxy_url)
                    await Actor.push_data(record)

            Actor.log.info(f"mode={mode}: {len(repo_ids)} {entity[:-1]}(s), maxConcurrency={max_concurrency}")
            await asyncio.gather(*(_bounded(r) for r in repo_ids))
            return

        if mode == "creator":
            usernames = [str(i) for i in (input_data.get("usernames") or [])]
            if input_data.get("username"):
                usernames.insert(0, str(input_data["username"]))
            if not usernames:
                raise input_error("Provide 'username' or 'usernames' when mode is 'creator'.")
            seen = set()
            usernames = [u for u in usernames if not (u in seen or seen.add(u))]
            account_type = input_data.get("accountType", "auto")

            max_concurrency = int(input_data.get("maxConcurrency", 4))
            sem = asyncio.Semaphore(max_concurrency)

            async def _bounded_creator(username: str):
                async with sem:
                    proxy_url = await proxy_config.new_url() if proxy_config else None
                    record = await run_creator(username, account_type, proxy_url)
                    await Actor.push_data(record)

            Actor.log.info(f"mode=creator: {len(usernames)} account(s), maxConcurrency={max_concurrency}")
            await asyncio.gather(*(_bounded_creator(u) for u in usernames))
            return

        # models / datasets / spaces (list/search modes)
        entity = LIST_ENTITY_BY_MODE[mode]
        proxy_url = await proxy_config.new_url() if proxy_config else None
        records = await run_list(entity, input_data, max_items, proxy_url)
        Actor.log.info(f"mode={mode}: {len(records)} record(s), maxItems={max_items}")
        await Actor.push_data(records)
