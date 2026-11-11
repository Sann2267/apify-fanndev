"""Offline + live checks for the group posts scraper.

    python test_local.py            # live: read two public groups
    python test_local.py --offline  # parser only, no network
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys

sys.path.insert(0, ".")

from src.fbcore import FacebookSession  # noqa: E402
from src.groups import GroupUnavailable, fetch_group, fetch_posts  # noqa: E402
from src.main import epoch_from_date, read_groups  # noqa: E402
from src.parser import collect_posts, group_ref, matches_filters, summarise  # noqa: E402


class Log:
    def info(self, message):
        print(f"  [info] {message}")

    def warning(self, message):
        print(f"  [warn] {message}")


def check(label, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {label}" + (f"  -- {detail}" if detail else ""))
    return bool(condition)


def b64(value: str) -> str:
    return base64.b64encode(value.encode()).decode()


def offline_checks() -> bool:
    ok = True
    ok &= check("group ref from URL",
                group_ref("https://www.facebook.com/groups/React.JSdevelopers/") == "React.JSdevelopers")
    ok &= check("group ref from id", group_ref("1873009809663604") == "1873009809663604")
    ok &= check("groups read from both inputs",
                read_groups({"groups": ["a"], "startUrls": [{"url": "facebook.com/groups/b"}]})
                == ["a", "b"])
    ok &= check("date parsed", epoch_from_date("2026-01-01") == 1767225600)

    # The join that holds the parser together: scattered nodes, one post.
    payload = {
        "a": {"id": b64("S:_I100001976425228:VK:3932422300389001"),
              "message": {"text": "hello group"}},
        "b": {"post_id": "3932422300389001",
              "permalink_url": "https://www.facebook.com/groups/x/posts/3932422300389001/",
              "creation_time": 1_760_000_000},
        "c": {"id": b64("feedback:3932422300389001"),
              "i18n_reaction_count": "43",
              "comments": {"total_count": 12},
              "share_count": {"count": 4},
              "owning_profile": {"name": "Someone", "id": "999"}},
    }
    posts = collect_posts(payload)
    ok &= check("scattered nodes joined into one post", len(posts) == 1, str(list(posts)))
    post = posts["3932422300389001"]
    ok &= check("text joined", post["text"] == "hello group")
    ok &= check("permalink joined", "posts/3932422300389001" in (post["postUrl"] or ""))
    ok &= check("counts joined",
                (post["reactionCount"], post["commentCount"], post["shareCount"]) == (43, 12, 4),
                str((post["reactionCount"], post["commentCount"], post["shareCount"])))
    ok &= check("author joined", post["authorName"] == "Someone")
    ok &= check("timestamp converted", post["createdAtIso"] is not None, str(post["createdAtIso"]))

    ok &= check("unknown reaction count fails a minimum",
                matches_filters({"reactionCount": None}, {"minReactions": 1}) is False)
    ok &= check("summary counts", summarise([post])["postsCollected"] == 1)
    return ok


async def live_checks() -> bool:
    ok = True
    async with FacebookSession(log=Log()) as session:
        print("\n-- a readable public group --")
        html, meta = await fetch_group(session, "React.JSdevelopers")
        ok &= check("group metadata read", bool(meta.get("groupId")), json.dumps(
            {k: meta.get(k) for k in ("groupId", "groupName", "memberCountLabel", "privacy")},
            ensure_ascii=False))
        posts, fetch_meta = await fetch_posts(session, html, meta["groupUrl"], 20, log=Log())
        ok &= check("posts returned", len(posts) >= 3, f"{len(posts)} posts in "
                                                       f"{fetch_meta['requestsMade']} request(s)")
        if posts:
            sample = posts[0]
            ok &= check("post has text or permalink", bool(sample["text"] or sample["postUrl"]))
            ok &= check("post has a timestamp", bool(sample["createdAtIso"]),
                        str(sample["createdAtIso"]))
            print("    sample:", json.dumps(
                {k: (str(sample[k])[:70] if sample[k] is not None else None)
                 for k in ("postId", "authorName", "reactionCount", "commentCount",
                           "createdAtIso", "text")}, ensure_ascii=False))
            ok &= check(
                "comment counts are reported even though bodies are not served",
                any(isinstance(p["commentCount"], int) for p in posts),
                str([p["commentCount"] for p in posts[:5]]),
            )

        print("\n-- a group that cannot be read logged-out --")
        try:
            await fetch_group(session, "zz-not-a-real-group-98765")
            ok &= check("unreadable group raises", False, "no exception")
        except GroupUnavailable as exc:
            ok &= check("unreadable group raises GroupUnavailable", True, str(exc)[:60])
    return ok


def main() -> int:
    print("== offline ==")
    ok = offline_checks()
    if "--offline" not in sys.argv:
        print("\n== live ==")
        ok = asyncio.run(live_checks()) and ok
    print("\nALL PASS" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
