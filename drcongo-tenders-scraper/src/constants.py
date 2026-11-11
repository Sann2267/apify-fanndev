"""Shared constants for the DR Congo public procurement scraper (SIGMAP).

See CRAWLING_METHOD.md for full recon notes. `marchepublic.cd` is a
JSF/PrimeFaces (Java) server-rendered application -- there is no JSON API and
no plain-GET listing URL. Browsing works only by replaying the exact
PrimeFaces AJAX protocol a real browser uses:

  1. GET  /portail/index.xhtml           -- primes a JSESSIONID + a fresh
                                             javax.faces.ViewState token.
  2. POST /portail/index.xhtml           -- a PrimeFaces.ab() AJAX postback
                                             simulating a click on one
                                             mega-menu item (`landing-menu:j_idtNN`).
                                             The server responds with a bare
                                             `<redirect url="/portail/publication.xhtml">`
                                             partial-response and stores which
                                             publication type was selected in
                                             the (session-scoped) backing bean.
  3. GET  /portail/publication.xhtml     -- same session/cookies -- renders a
                                             PrimeFaces DataView grid of
                                             whatever publication type step 2
                                             selected.

The ViewState is single-use/stateful, so this client re-primes it (step 1)
before every category click rather than trying to reuse one across requests.
"""

BASE = "https://marchepublic.cd/portail"
INDEX_URL = f"{BASE}/index.xhtml"
PUBLICATION_URL = f"{BASE}/publication.xhtml"

# Every leaf item in the site's own "Publications" mega-menu, in the order
# they appear on the page, grouped exactly as marchepublic.cd groups them
# (PPM / AAO / AMI / ANO+AS / APPROBATION / ATTESTATION DE REDEVANCE). The
# `jsf_id` is the literal PrimeFaces component id (`landing-menu:j_idtNN`)
# this actor "clicks" via an AJAX postback -- these ids are assigned by JSF
# at compile time from the page's own component tree order and are stable
# across requests/sessions (confirmed identical across many fresh recon
# sessions), but would need re-discovery if ARMP ever redeploys the portal
# with a restructured menu.
LIST_CONFIGS = {
    "procurement_plan": {
        "jsf_id": "landing-menu:j_idt22",
        "title": "Plans de passation des marches (PPM)",
        "group": "PPM",
    },
    "call_for_tenders": {
        "jsf_id": "landing-menu:j_idt24",
        "title": "Avis d'appel d'offres",
        "group": "AAO",
    },
    "tender_postponement": {
        "jsf_id": "landing-menu:j_idt25",
        "title": "Avis de report (AAO)",
        "group": "AAO",
    },
    "tender_addenda": {
        "jsf_id": "landing-menu:j_idt26",
        "title": "Additifs DAO",
        "group": "AAO",
    },
    "tender_cancellation": {
        "jsf_id": "landing-menu:j_idt27",
        "title": "Avis d'annulation (AAO)",
        "group": "AAO",
    },
    "tender_unsuccessful": {
        "jsf_id": "landing-menu:j_idt28",
        "title": "Declaration d'infructuosite (AAO)",
        "group": "AAO",
    },
    "tender_provisional_award": {
        "jsf_id": "landing-menu:j_idt29",
        "title": "Avis d'attribution provisoire (AAO)",
        "group": "AAO",
    },
    "tender_final_award": {
        "jsf_id": "landing-menu:j_idt30",
        "title": "Avis d'attribution definitive (AAO)",
        "group": "AAO",
    },
    "tender_contract_termination": {
        "jsf_id": "landing-menu:j_idt31",
        "title": "Resiliation contrat (AAO)",
        "group": "AAO",
    },
    "expression_of_interest": {
        "jsf_id": "landing-menu:j_idt34",
        "title": "Avis a manifestation d'interet",
        "group": "AMI",
    },
    "ami_postponement": {
        "jsf_id": "landing-menu:j_idt35",
        "title": "Avis de report (AMI)",
        "group": "AMI",
    },
    "ami_cancellation": {
        "jsf_id": "landing-menu:j_idt36",
        "title": "Avis d'annulation (AMI)",
        "group": "AMI",
    },
    "ami_addenda": {
        "jsf_id": "landing-menu:j_idt37",
        "title": "Additifs DP",
        "group": "AMI",
    },
    "ami_unsuccessful": {
        "jsf_id": "landing-menu:j_idt38",
        "title": "Declaration d'infructuosite (AMI)",
        "group": "AMI",
    },
    "ami_provisional_award": {
        "jsf_id": "landing-menu:j_idt39",
        "title": "Avis d'attribution provisoire (AMI)",
        "group": "AMI",
    },
    "ami_final_award": {
        "jsf_id": "landing-menu:j_idt40",
        "title": "Avis d'attribution definitive (AMI)",
        "group": "AMI",
    },
    "ami_recruitment_notice": {
        "jsf_id": "landing-menu:j_idt41",
        "title": "Avis de recrutement (AMI)",
        "group": "AMI",
    },
    "ami_contract_termination": {
        "jsf_id": "landing-menu:j_idt42",
        "title": "Resiliation contrat (AMI)",
        "group": "AMI",
    },
    "non_objection_notice": {
        "jsf_id": "landing-menu:j_idt45",
        "title": "Avis de Non Objection (ANO)",
        "group": "ANO_AS",
    },
    "special_authorization": {
        "jsf_id": "landing-menu:j_idt46",
        "title": "Autorisation Speciale (AS)",
        "group": "ANO_AS",
    },
    "approval_decision": {
        "jsf_id": "landing-menu:j_idt48",
        "title": "Decision d'approbation",
        "group": "APPROBATION",
    },
    "levy_certificate": {
        "jsf_id": "landing-menu:j_idt50",
        "title": "Attestation de redevance",
        "group": "ATTESTATION_REDEVANCE",
    },
}

VALID_LIST_TYPES = tuple(LIST_CONFIGS.keys()) + ("all",)

TLS_PROFILE = "chrome124"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

AJAX_HEADERS = {
    **HEADERS,
    "Faces-Request": "partial/ajax",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "application/xml, text/xml, */*; q=0.01",
    "Referer": INDEX_URL,
}

MAX_RETRIES = 3
RETRY_DELAY_BASE = 2.0
