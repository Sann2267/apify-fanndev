"""Shared constants for the ARMP (Autorite de Regulation des Marches Publics)
Madagascar e-GP scraper.

See CRAWLING_METHOD.md for the full recon writeup. Short version: ARMP's
public procurement portal is a plain server-rendered PHP site (no CMS/JS
framework, PHP/7.4.33, nginx). No robots.txt exists at all (`GET
/robots.txt` returns a plain 404 -- treated as "nothing disallowed", same
convention as every other actor in this portfolio). No WAF/CDN fingerprint
observed on any endpoint; a plain HTTP client with no TLS impersonation
already clears every page tested. `curl_cffi` is used anyway for portfolio
consistency and residential-proxy compatibility.

The site's HTTPS certificate does not match its hostname (SNI/cert-chain
mismatch on both `www.armp.mg` and `marches.armp.mg`), while plain HTTP on
port 80 serves the identical content from the same server -- this actor
uses `http://` throughout rather than disabling TLS verification.

Three public, no-login data sources were confirmed live:

1. **avis** -- `GET /marches_publics/index.php`: today's live calls for
   tender ("avis d'appel d'offres"), grouped into one big page by the 22
   administrative regions of Madagascar (~420-450 rows total at any time).
2. **dossiers** -- `POST /marches_publics/dossier_sub_list_modal.php`: the
   full multi-year dossier archive (2015-present), searchable by year
   (the only filter this actor exposes; category/entity/procurement-type/
   mode filters exist upstream but are left as wildcards to keep the
   actor's input simple). Each row also carries a Bootstrap modal with a
   few extra fields (dossier date, financing source, PRMP officer name)
   which this actor merges into the same record at no extra request cost.
   PHP notices/warnings are printed as raw HTML comments at the top of
   this endpoint's response body on every request (observed even with a
   clean wildcard query) -- cosmetic upstream noise, stripped before
   parsing rather than treated as an error.
3. **contrats** -- `POST /marches_publics/contrat_action.php`: a genuine
   JSON endpoint (`Content-Type: application/json`) listing awarded
   contracts with the winning supplier's name, tax ID (NIF), *declared
   beneficial owner* (a rare transparency field), contract amount, and
   currency.

A "Search and Export to Excel" button on the dossier-archive page is wired
(in a `<!-- commented out -->` block in the page's own HTML, i.e. not even
reachable from the rendered UI) to a `connexion.php` login redirect --
this is a premium export convenience, not a viewing gate: both `GET
index.php` and the plain "Rechercher" (Search) button that actually
renders on the page require no account at all.

Quirk worth flagging: `dossier_sub_list_modal.php` has no server-side
pagination -- one query returns the *entire* matching result set in a
single HTML response (each row's modal duplicates a fair amount of
markup, so an unfiltered full historical year like 2025 was ~97 MB and
took over a minute to download). This actor caps how many rows it *keeps*
via `maxResults`, but the full page for whichever year you request is
always downloaded first -- pick a specific year rather than requesting
many years back-to-back in one run if the archive matters for your use
case.
"""

BASE = "http://www.armp.mg/marches_publics"

AVIS_URL = f"{BASE}/index.php"
DOSSIERS_URL = f"{BASE}/dossier_sub_list_modal.php"
CONTRATS_URL = f"{BASE}/contrat_action.php"

VALID_LIST_TYPES = ("avis", "dossiers", "contrats")

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2.0

# dossiers/contrats POST bodies for filters this actor doesn't expose in its
# input -- always wildcarded so a plain year query returns every category/
# entity/procurement-type/mode for that year.
DOSSIERS_WILDCARD_FIELDS = {"categorie": "", "entite": "", "typemarche": "", "passation": ""}
CONTRATS_WILDCARD_FIELDS = {"ENTITE_CATEGORIE": "%", "ENTITE": "%", "REGION": "%", "TYPE": "%", "MODE": "%"}
