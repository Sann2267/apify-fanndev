# Crawling method — Facebook groups

Measured 2026-09-20, curl_cffi, no proxy, no login, exit IP Indonesia.

## A group page is a shell; the posts arrive afterwards

`GET /groups/<slug-or-id>` returns HTTP 200 for everything — a real group, a
private group, and a slug that does not exist. Size is the discriminator:

| Payload | Meaning |
| --- | --- |
| ~330 KB | shell only: private, missing, or not readable logged out |
| 0.9–1.2 MB | a readable group: metadata present, feed marked `"complete": false` |

Even in the readable case the HTML carries no posts. The feed block is
server-rendered as a placeholder holding one `GroupsSectionHeaderUnit` and a
cursor. Verified across five groups: `1611587095819757` and
`VintageComputerFederation` came back hollow, `PythonProgrammingLanguage` and
`React.JSdevelopers` readable.

## Replaying Facebook's own feed query

The readable page publishes the query the browser is about to run, with its id
*and* its variables:

```json
{"queryID": "28192873003712398",
 "variables": {"groupID": "1873009809663604", "regular_stories_count": 2, ...},
 "queryName": "CometGroupDiscussionRootSuccessQuery"}
```

`POST /api/graphql/` with those variables — `regular_stories_count` raised from
2 to 12 — returns the first batch of posts. Pagination then uses
`GroupsCometFeedRegularStoriesPaginationQuery`, whose id is not in the HTML but
is in the page's JS bundle as
`__d("GroupsCometFeedRegularStoriesPaginationQuery_facebookRelayOperation",[],...exports="28713663144987243")`.

Both ids are harvested per run. A pinned id would fail silently after Facebook's
next deploy, and a silent failure here looks exactly like "this group has no
posts".

## One post is scattered across four nodes

Facebook does not return a post as one object. In a single feed payload:

- the **body text** sits in a node whose only other key is an `id`
- the **permalink, `post_id` and `creation_time`** sit in the story node
- the **author** sits under `feedback_context.feedback_target_with_context.owning_profile`
- the **reaction / comment / share counts** sit inside
  `comet_ufi_summary_and_actions_renderer`, whose wrapper has no id of its own

What ties them together is the base64 `id` each id-bearing node carries:

```
UzpfSTEwMDAwMTk3NjQyNTIyODpWSzozOTMyNDIyMzAwMzg5MDAx
  -> "S:_I100001976425228:VK:3932422300389001"
ZmVlZGJhY2s6MzkzMjQyMjMwMDM4OTAwMQ==
  -> "feedback:3932422300389001"
```

Both end in the post id. So the parser makes one pass over every dict, decodes
whatever id it finds, and files each field under the post it names — no path
walking anywhere.

**Gotcha that cost a test:** reading engagement only off the id-bearing node
returns `commentCount: null` for posts that plainly have comments, because the
counts live one level deeper inside the renderer wrapper. Feedback nodes get a
bounded subtree scan for exactly that reason.

## Comment bodies are not served to logged-out clients

Three routes tried, all on public groups:

1. **Feed payload** — `can_viewer_comment: false`, renderer is
   `UnauthenticatedUCometUFISummaryAndActionsRenderer`, no comment edges.
2. **Post permalink** (`/groups/<gid>/posts/<pid>/`) — `comments.total_count`
   populated, `comments.edges` empty.
3. **`CommentsListComponentsPaginationQuery`** — doc_id `28874791392118765`
   harvested from the bundle; every variable combination tried returned the same
   `missing_required_variable_value` error with an identical `mid`, i.e. a fixed
   refusal rather than a variables problem.

For contrast, the same check on a **Page** post (`/dominos/posts/<id>`) returns
10 comment bodies in SSR with `total_count: 162`. So the gating is specific to
groups, not to comments in general.

The actor therefore reports `commentCount` (real) and `commentsServed` (what was
returned) as two separate fields, and `scrapeComments` defaults to off.

## Cost shape

One HTTP request for the shell, one GraphQL call per ~12 posts, plus a one-off
bundle fetch the first time pagination is needed in a session. No proxy, no
browser.
