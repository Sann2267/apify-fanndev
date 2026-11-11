# Crawling method — Facebook reels and videos

Measured 2026-09-20, curl_cffi, no proxy, no login, exit IP Indonesia.

## Three surfaces, all server-rendered

| URL | Size | What it carries |
| --- | --- | --- |
| `/{slug}/reels/` | ~13 MB | 10 reels: `play_count_reduced`, track, MP4 URLs, captions |
| `/{slug}/videos` | ~940 KB | videos tab, with **exact** `play_count` integers |
| `/watch/?v=<id>` | ~880 KB | 302 to `/{page}/videos/<id>/` — a universal id resolver |

The watch redirect is what makes a bare id usable: a caller does not have to
know whether `1053159700187202` is a reel or a page video.

## A video is scattered; the join is its numeric id

```json
{"id": "637979908801309", "browser_native_hd_url": "...", "browser_native_sd_url": "..."}
{"video": {"id": "637979908801309", "first_frame_thumbnail": "..."},
 "shareable_url": "https://www.facebook.com/reel/637979908801309",
 "playback_video": {"length_in_second": 39.248, "width": 1080, "height": 1920},
 "video_owner": {"name": "Domino's Pizza", "id": "100064795448235"},
 "play_count_reduced": "292K", "track_title": null,
 "is_original_audio_on_facebook": true}
{"id": "637979908801309", "captions_url": "...srt",
 "video_available_captions_locales": [...]}
{"__typename": "Story", "id": "<base64 S:_I...:VK:637979908801309>",
 "post_id": "1053159700187202", "creation_time": 1737990015}
```

**Gotcha, and the reason this parser makes two passes.** A bare numeric `id` is
not enough to call a node a video: `video_owner` carries the *page's* numeric id
in exactly the same shape, and treating it as a video invents a phantom record
keyed by the page — which the offline test caught.

So pass one identifies real videos, by requiring one of
`browser_native_hd_url`, `captions_url`, `play_count`, `play_count_reduced`,
`playable_duration_in_ms`… alongside the id, or by reading the id out of a
`shareable_url` or a decoded base64 story id. Pass two then attaches fields from
nodes whose only link is a bare `id` that pass one already proved is a video's.
Dropping pass two loses the title and the owner; skipping pass one's marker
check invents videos.

## Play counts: two different numbers

- Reels tab: `play_count_reduced: "292K"` — an abbreviation.
- Videos tab: `play_count: 270777` — exact.

Both are emitted: `playCount` (parsed) and `playCountLabel` (verbatim). An exact
integer always overwrites a parsed abbreviation when both are present for the
same video.

## Transcripts come from Facebook's own caption files

`captions_url` is a signed CDN link to a real SubRip file. Fetched, it returns:

```
1
00:00:00,661 --> 00:00:05,481
You think you know Domino's but
when it's mission critical,
```

`video_available_captions_locales[]` lists additional tracks with a
`localized_creation_method` such as *"Terjemahan otomatis"* (automatic
translation), so the output can say where a transcript came from.

Measured on one page's reels tab: 4 of 10 reels had a caption file, and all four
downloaded and parsed. `transcript_urls` exists as a field but was `null`
throughout; `captions_url` is the one that works.

Videos with no caption file get `transcript: null`. No speech recognition is
performed — inventing a transcript would be worse than not having one.

## Pagination

`ProfileCometAppCollectionReelsRendererPaginationQuery` and
`PagesCometChannelTabAllVideosCardImplPaginationQuery` are read from the page's
JS bundles, with the cursor taken from the rendered `page_info`. Where the
replay does not succeed, the actor keeps the rendered tab, logs a warning, and
returns a smaller honest answer rather than failing.

## Existence check

Facebook answers HTTP 200 for a slug or video id that does not exist and serves a
~330 KB shell, so size is the discriminator. A watch URL that resolves to a page
carrying only *related* videos is also rejected: returning somebody else's video
under the requested id would be worse than an error.

## Cost shape

~13 MB for a reels tab, ~940 KB for a videos tab, ~880 KB per direct video, plus
a few KB per transcript. No proxy, no browser, no transcription service.
