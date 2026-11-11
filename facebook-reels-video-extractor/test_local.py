"""Offline + live checks for the reels and video extractor.

    python test_local.py            # live: a reels tab, a videos tab, one transcript
    python test_local.py --offline  # parser only, no network
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys

sys.path.insert(0, ".")

from src.fbcore import FacebookSession  # noqa: E402
from src.main import read_targets  # noqa: E402
from src.parser import (  # noqa: E402
    collect_videos,
    matches_filters,
    page_ref,
    parse_srt,
    summarise,
    video_id,
)
from src.videos import add_transcript, fetch_single, fetch_tab  # noqa: E402


class Log:
    def info(self, message):
        print(f"  [info] {message}")

    def warning(self, message):
        print(f"  [warn] {message}")


def check(label, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {label}" + (f"  -- {detail}" if detail else ""))
    return bool(condition)


def offline_checks() -> bool:
    ok = True
    ok &= check("id from reel URL",
                video_id("https://www.facebook.com/reel/637979908801309") == "637979908801309")
    ok &= check("id from watch URL",
                video_id("https://www.facebook.com/watch/?v=10153231379946729")
                == "10153231379946729")
    ok &= check("id from videos URL",
                video_id("https://www.facebook.com/facebook/videos/10153231379946729/")
                == "10153231379946729")
    ok &= check("page slug not mistaken for a video", page_ref("dominos") == "dominos")
    ok &= check("video URL not mistaken for a page",
                page_ref("https://www.facebook.com/reel/637979908801309") is None)

    slugs, ids = read_targets({"pages": ["dominos"],
                               "videoUrls": ["https://www.facebook.com/reel/123456789"]})
    ok &= check("input split into pages and videos",
                slugs == ["dominos"] and ids == ["123456789"], f"{slugs} {ids}")

    vid = "637979908801309"
    payload = {
        "media": {"id": vid,
                  "browser_native_hd_url": "https://video/hd.mp4",
                  "browser_native_sd_url": "https://video/sd.mp4"},
        "reel": {"video": {"id": vid, "first_frame_thumbnail": "https://img/t.jpg"},
                 "shareable_url": f"https://www.facebook.com/reel/{vid}",
                 "playback_video": {"length_in_second": 39.248, "width": 1080, "height": 1920},
                 "video_owner": {"name": "Domino's Pizza", "id": "100064795448235"},
                 "play_count_reduced": "292K",
                 "is_original_audio_on_facebook": True,
                 "total_comment_count": 12},
        "caps": {"id": vid, "captions_url": "https://cdn/x.srt"},
        "story": {"id": base64.b64encode(f"S:_I100064795448235:VK:{vid}".encode()).decode(),
                  "post_id": "1053159700187202", "creation_time": 1_737_990_015,
                  "message": {"text": "Operation Loaded Chicken is a go."},
                  "i18n_reaction_count": "430"},
    }
    videos = collect_videos(payload)
    ok &= check("scattered nodes joined into one video", len(videos) == 1, str(list(videos)))
    video = videos[vid]
    ok &= check("abbreviated play count parsed", video["playCount"] == 292000)
    ok &= check("raw label kept", video["playCountLabel"] == "292K")
    ok &= check("permalink and reel flag", video["isReel"] is True)
    ok &= check("duration", video["lengthSeconds"] == 39.25, str(video["lengthSeconds"]))
    ok &= check("owner", video["pageName"] == "Domino's Pizza")
    ok &= check("mp4 urls", bool(video["videoHdUrl"] and video["videoSdUrl"]))
    ok &= check("caption text joined from the story node",
                video["caption"] == "Operation Loaded Chicken is a go.")
    ok &= check("engagement total", video["engagementTotal"] == 442,
                str(video["engagementTotal"]))
    ok &= check("engagement rate", video["engagementRatePercent"] == 0.151,
                str(video["engagementRatePercent"]))
    ok &= check("captions flagged", video["hasCaptions"] is True)

    srt = ("1\n00:00:00,661 --> 00:00:05,481\nYou think you know Domino's but\n"
           "when it's mission critical,\n\n2\n00:00:05,481 --> 00:00:11,001\n"
           "it's not the pizza we send in.\n")
    transcript, cues = parse_srt(srt)
    ok &= check("srt parsed into cues", len(cues) == 2, str(len(cues)))
    ok &= check("transcript joined",
                transcript.startswith("You think you know Domino's but when it's"),
                transcript[:50])

    ok &= check("unknown play count fails a minimum",
                matches_filters({"playCount": None}, {"minPlays": 1}) is False)
    ok &= check("summary", summarise([video])["withCaptions"] == 1)
    return ok


async def live_checks() -> bool:
    ok = True
    async with FacebookSession(log=Log()) as session:
        print("\n-- reels tab --")
        reels, meta = await fetch_tab(session, "dominos", "reels", 10, log=Log())
        ok &= check("reels returned", len(reels) >= 5, f"{len(reels)} in "
                                                       f"{meta['requestsMade']} request(s)")
        with_plays = [r for r in reels if r["playCount"] is not None]
        ok &= check("play counts present", len(with_plays) >= 5,
                    str([r["playCountLabel"] for r in reels[:5]]))
        with_mp4 = [r for r in reels if r["videoHdUrl"]]
        ok &= check("direct mp4 urls present", len(with_mp4) >= 5, f"{len(with_mp4)}")

        captioned = [r for r in reels if r["hasCaptions"]]
        ok &= check("some reels carry captions", len(captioned) >= 1, f"{len(captioned)}")
        if captioned:
            await add_transcript(session, captioned[0])
            ok &= check("transcript downloaded and parsed",
                        bool(captioned[0].get("transcript")),
                        (captioned[0].get("transcript") or "")[:80])

        print("\n-- videos tab (exact play counts) --")
        videos, _ = await fetch_tab(session, "dominos", "videos", 10, log=Log())
        ok &= check("videos returned", len(videos) >= 3, str(len(videos)))
        exact = [v for v in videos if isinstance(v["playCount"], int)]
        ok &= check("exact play counts present", len(exact) >= 1,
                    str([v["playCount"] for v in exact[:5]]))

        print("\n-- one video by id, via the watch resolver --")
        single = await fetch_single(session, "10153231379946729")
        ok &= check("single video resolved", single["videoId"] == "10153231379946729")
        print("    ", json.dumps({k: single.get(k) for k in
                                  ("title", "pageName", "playCount", "lengthSeconds",
                                   "hasCaptions", "createdAtIso")}, ensure_ascii=False))
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
