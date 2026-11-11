"""Endpoints, headers, and recon summary -- all in one place.

Recon summary (2026-08-26/27): CIPA -- Botswana's Companies and Intellectual
Property Authority (cipa.co.bw) -- runs the public marketing site on
WordPress (`www.cipa.co.bw`, plain `nginx`, no WAF/CAPTCHA observed anywhere)
and its transactional "Online Business Registration System" (OBRS) on
**Verne by Foster Moore** (footer: "Powered by Foster Moore"), a citizen-
services platform used by many small-country government registries. The
Verne app lives at `/master/...` (search) and `/companies/...` (entity
profile), same origin/domain as the WordPress site, same robots.txt.

`robots.txt` is a stock WordPress block (`Disallow: /wp-admin/`, `Allow:
/wp-admin/admin-ajax.php`) -- no Claude/AI-crawler mention, no disallow for
`/master/` or `/companies/`.

**"Search the Register" (`/master/ui/start/CIPARegisterSearch`) is public --
no login required.** It is rendered as a Vue3 SPA ("Verne") that talks to a
stateful JSON-RPC-ish endpoint (`POST /master/ui/<transactionId>`) using a
custom compact serialization (looks like XML but tag names are hex node IDs,
so it is NOT well-formed XML -- see `extractor.py`'s `parse_delta_state`).
Confirmed live as a **guest** session (`Catalyst.usr.type == "guest"`):

1. `GET /master/ui/start/CIPARegisterSearch` -> redirects to
   `/master/ui/<transactionId>`. The response HTML embeds the full initial
   view tree as a plain JS var: `var viewTree = {...};` -- this is clean
   JSON, parsed directly (no need for a throwaway POST to "prime" state).
2. `POST /master/ui/<transactionId>` with
   `{"returnRootHtmlOnChange": false, "returnChangesOnly": true, "commands":
   [{"type": "view-node-set-attribute-value", "id": <NameOrNumber field id>,
   "value": "<query>"}]}` -- sets the search box value server-side.
3. `POST` again with `commands: [{"type": "view-node-button-click", "id":
   <Search button id>}]` -- executes the search. **Both `commands[].type`
   values (`view-node-set-attribute-value`, `view-node-button-click`) were
   reverse-engineered from the shipped `catalyst.002.api.oo.js` /
   `catalystui.js` bundles**, not guessed.

**Critical gotcha found during recon:** the client config embedded in the
page (`Catalyst.returnRootHtmlOnChange = false; Catalyst.delta = true;`)
must be honored -- i.e. `returnRootHtmlOnChange: False, returnChangesOnly:
True` on every POST. Sending the opposite (`true`/`false`, which seemed like
the more "complete" option) still returns HTTP 200 with a well-formed but
**silently empty** results box on every query tried (including common terms
like "Bank", "Botswana", "First") -- looks like success, isn't. This is not
documented anywhere in the JS; only found by diffing the two flag
combinations against a query guaranteed to have real matches.

Real search results (delta-mode) include a labeled "hyperlink" button per
match (`"<Name> (<CompanyNumber>)"`, e.g. `"Bank Gaborone Limited
(BW00000015806)"`). A `view-node-button-click` on that button's node id
returns `{"redirect": "https://www.cipa.co.bw/companies/ui/start/entityView/
<32-hex-id>?dom=Company"}`.

**That `entityView` URL is a real public permalink -- confirmed to load with
HTTP 200 from a completely fresh session (no cookies at all)**, so the
detail-fetch step needs no session affinity with the search step. Its HTML
embeds the same `var viewTree = {...}` pattern, this time real, clean JSON
(no delta-parsing needed) describing the FULL company profile: registration
number, status, entity type, registered office / postal / physical / mail
addresses, and -- notably -- Directors, Secretary, Shareholders, Auditor,
Beneficial Owners (each with name/nationality/address), and per-shareholder
`ShareAllocation`. This is a complete, free, public beneficial-ownership
registry lookup -- no login, no CAPTCHA, no paywall encountered anywhere in
this flow.

A zero-match query (garbage string) returns a clean, distinguishable
`nodetype: "searchResults"` / `text.noResults: "Your search returned no
results"` marker instead of a server error -- used by `extractor.py` to
emit a `_error: "not_found"` record instead of raising.

The separate "Trademark & Patent Search" link on the homepage
(`http://ipsearch.cipa.co.bw/wopublish-search/`) is **dead** -- plain Apache
Tomcat 8.0.0-RC5 404 on that exact path (root `/` on that host is a bare
default IIS page), confirmed on both `http://` and `https://` (the latter
doesn't even accept a TCP connection on 443). Out of scope for this actor.
"""

TLS_PROFILE = "chrome124"

BASE_URL = "https://www.cipa.co.bw"
SEARCH_START_URL = f"{BASE_URL}/master/ui/start/CIPARegisterSearch"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Entity-type filter values accepted by the search form's `EntityType`
# dropdown (`DC_registerSearchEntityType` lookup dictionary observed on the
# search page).
ENTITY_TYPES = ["any", "businessName", "private", "public", "external", "close"]

MAX_RETRIES = 5
RETRY_DELAY_BASE = 1.0
