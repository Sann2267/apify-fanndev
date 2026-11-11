# Crawling method: Steam profiles & achievements (recon 2026-10-11)

## WAF profile

**No WAF and no fingerprint gate.** Plain python-requests TLS gets 200 on every surface below.
robots.txt (steamcommunity.com) disallows only `/actions/ /linkfilter/ /tradeoffer/ /trade/ /email/`.
`api.steampowered.com` robots disallows `/`, but it is Valve's documented Web API and we only use
three keyless methods (same precedent as steam-concurrent-players-monitor).

The only gates are **rate limits**:

| Surface | Limit | Recovery | Keyed on |
|---|---|---|---|
| steamcommunity HTML (profile, friends, badges) | HTTP 429 (29 KB HTML) after ~120 requests in ~6 s | ~43-60 s | **IP only**: fresh sessions with safari17_0/firefox133 stayed 429 |
| same, if you keep hammering | Akamai 403 "Access Denied" (414 B, `server: AkamaiGHost`), also hits `?xml=1` | ~20 s | **IP + TLS fingerprint**: chrome124 403 while safari17_0/firefox133 got 200 from the same IP at the same moment |
| `?xml=1` profiles, `/stats/` XML, `GetGameAchievements` | none observed: 300 / 200 / 100 requests @ c10 | n/a | n/a |

The client therefore has a separate HTML semaphore (2 without a proxy), waits 45 s on HTML 429
(direct) or rotates the exit IP (proxy). On a 403 it rotates the TLS profile with short backoffs
first and waits 25 s only if the 403 persists. Measured direct throughput once the burst is spent:
250 profiles with page enrichment in 567 s (21 rate-limit waits, 0 failures).

**Bug found in testing:** closing a rotated-out `AsyncSession` while sibling tasks still had
requests in flight on it returned `status_code == 0` responses. Retired pools are now closed only at
the end of the run, and status 0 is treated as a transport retry.

## Surfaces

| Data | Request | Notes |
|---|---|---|
| Profile | `GET /profiles/{id64}?xml=1` or `/id/{vanity}?xml=1` | steamID64, name, avatar, privacy, vacBanned, tradeBanState, isLimitedAccount, memberSince, location, realname, summary, groups, `mostPlayedGames` (statsName, hoursPlayed = 2 weeks, hoursOnRecord). Unknown user → **HTTP 200** `<response><error>The specified profile could not be found.` |
| Profile page | `GET /profiles/{id64}/` | level (`.persona_level .friendPlayerLevelNum`), `.profile_count_link` counts, favourite badge, `.recent_game` blocks (hrs on record, last played, "N of M" achievements), `.recentgame_quicklinks` "N hours past 2 weeks", `.showcase_stats_row .showcase_stat` |
| Player achievements | `GET /profiles/{id64}/stats/{appid or statsName}/?tab=achievements&xml=1` | per achievement `closed`, apiname, name, desc, `unlockTimestamp`, icons; `<stats><hoursPlayed>` |
| Achievement schema + rarity | `GET api.steampowered.com/IPlayerService/GetGameAchievements/v1/?appid=&language=` | **keyless**. internal_name, localized name/desc (incl. hidden ones), hidden, `player_percent_unlocked` (1 decimal), icons, archived. Unknown app / no achievements → `{"response":{}}` |
| Game name | `IStoreBrowseService/GetItems/v1/?input_json=` | keyless; `success:15` = no store item |
| Equipped items | `IPlayerService/GetProfileItemsEquipped/v1/?steamid=` | keyless; relative asset paths under `community_assets/images/` |
| Friends | `GET /profiles/{id64}/friends/` | all friends on one page (294 tested), `.friend_block_v2[data-steamid]`; `g_rgCounts.cFriends` = total |
| Badges | `GET /profiles/{id64}/badges/?p=N` | 150 rows/page, "Showing 1-150 of 6,506 badges"; row id `badge_gamebadge_{appid}_{foil}_0` / `badge_badge_{id}` |
| Group members | `GET /groups/{name}/memberslistxml/?xml=1&p=N` (or `/gid/{id}/`) | 1000 ids/page, totalPages, nextPageLink. Unknown group → 200 `<response><error>` |

### Keyed Web API methods (NOT usable)

`GetOwnedGames`, `GetRecentlyPlayedGames`, `GetSteamLevel`, `GetBadges`, `GetPlayerSummaries`,
`GetFriendList`, `GetPlayerBans`, `ResolveVanityURL`, `GetSchemaForGame`, `GetTopAchievementsForGames`,
`GetCommunityBadgeProgress` → 400/401/403 without `key=`. `GetAchievementsProgress` is POST-only and 401.

## Traps (all return plausible 200s)

1. **Owned-games list is login-gated** in 2026: `/games/?tab=all`, `?xml=1`, `?tab=recent` all
   redirect to Sign In. Only recently played games (XML `mostPlayedGames` + profile page) are public.
2. **Hollow stats XML.** `/stats/{appid}/?tab=achievements&xml=1` answers for ANY appid, owned or
   not, and for profiles whose *game details* are private: full achievement list, all `closed="0"`,
   `hoursPlayed 0`, `privacyState public`. Unowned, hidden and genuine-zero are byte-for-byte alike.
   The tell is the profile page: the **"Games" count link exists only when game details are public**
   (4/4 public vs 0/2 hidden). With game details public, a 0-unlock / 0-hour game is still emitted
   but flagged `ownershipConfirmed: false`.
3. `<hoursPlayed>` in stats XML and `mostPlayedGame/hoursPlayed` are **last-2-weeks** hours (matched
   the review API's `playtime_last_two_weeks` on every non-zero sample), not lifetime.
4. Profile XML `<hoursPlayed2Wk>` reads **0.0** even when mostPlayedGames shows 29.8 h. The profile
   page's "N hours past 2 weeks" is authoritative (62.2) and differs from the XML sum (59.2) because
   the XML lists only a few games.
5. **Legacy Valve games redirect** `/stats/440/` → `/stats/TF2` (also CSGO, Portal2, L4D2) and the
   redirect **drops `?xml=1`**, so HTML comes back. Retry on the friendly name (learned and cached).
   An app without stats (Dota 2) or a bogus appid redirects to the profile root.
6. API names differ in case: stats XML `ach00`, API `ACH00`. Join case-insensitively.
7. Stats XML ignores `l=`. Localized names come from `GetGameAchievements&language=`.
8. A hidden friends list still renders the page with "Sorry, there are no players to show." Only the
   missing `.friends_nav a[data-navid="friends"]` tells hidden from empty.
9. The profile page's `.profile_ban_status` is **empty even for VAC-banned accounts** (8% of a gmod
   group sample). Only the XML `vacBanned` flag is available; no ban count or days since ban.
10. Dates drop the year when it is the current year ("10 Oct", "29 Sep @ 9:09pm"); a December date seen
    in January belongs to last year. Times of day are in an unstated zone, so only dates are emitted.
11. The XML `privacyState` can say `public` while the page renders private (1 of 168 in a cloud
    run): `.profile_page` carries class `private_profile` and the `.profile_private_info` box is
    EMPTY. Use the class, not the message. Emitted as `profilePagePrivate`.
12. Profile XML for non-public profiles carries only name, avatar, privacy and ban flags. The profile
    page adds nothing, so it is skipped to save the rate-limited HTML budget.

## Architecture

One actor, `mode` input (6 modes). All modes share the SteamID resolver (SteamID64 / URL / vanity /
STEAM_X:Y:Z / [U:1:N] / account id), the client and the HTML pacing, and a profile lookup is a
pre-step for four of them, so splitting into six actors would duplicate all of it.
