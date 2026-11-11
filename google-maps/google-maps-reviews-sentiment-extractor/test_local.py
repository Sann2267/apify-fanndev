"""Local smoke test: runs the actor end-to-end against live Google."""
import asyncio, json, os, pathlib, sys

os.environ.setdefault("APIFY_LOCAL_STORAGE_DIR", "./storage")

INPUT = json.loads(pathlib.Path("_input.json").read_text(encoding="utf-8")) if pathlib.Path("_input.json").exists() else {
    "placeIds": ["ChIJrTLr-GyuEmsRBfy61i59si0"],
    "proxyConfiguration": {"useApifyProxy": False},
}


async def run():
    os.makedirs("storage/key_value_stores/default", exist_ok=True)
    with open("storage/key_value_stores/default/INPUT.json", "w", encoding="utf-8") as fh:
        json.dump(INPUT, fh)
    from src.main import main
    await main()


if __name__ == "__main__":
    asyncio.run(run())
