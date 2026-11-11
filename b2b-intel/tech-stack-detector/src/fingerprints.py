"""The fingerprint table.

Deliberately small. Wappalyzer tracks ~2,000 technologies and most of them
never appear in a lead list; this table covers the ones a B2B prospecting or
competitive-research buyer actually filters on, and every signal below was
either observed live during recon (2026-09-20) or is a vendor-documented,
long-stable marker.

Signal types, in descending order of how much they prove:

    header     an HTTP response header name, optionally with a value substring.
               Hard to fake accidentally.
    cookie     a cookie name the site sets. Also hard to fake.
    generator  the <meta name="generator"> content. Self-declared but reliable.
    host       a third-party host referenced by <script src> or <link href>.
               The workhorse: most SaaS is embedded this way.
    html       a substring in the markup. Weakest, so these are chosen to be
               strings nothing else plausibly contains.

Confidence is per signal, not per technology, because the same technology can
be proven or merely suggested depending on which marker turned up:

    confirmed  the signal is specific to this vendor and essentially unforgeable
               by coincidence (a vendor cookie, a vendor CDN host).
    likely     consistent with the technology but shared with others, or
               self-declared (a generic header value, a common path fragment).

A technology is reported as `confirmed` if any confirmed signal matched, else
`likely`. Every match carries the evidence that produced it, so a buyer can
audit a result instead of trusting a label.
"""

from __future__ import annotations

# category -> what the buyer is usually asking when they filter on it
CATEGORIES = {
    "Ecommerce": "Store platform",
    "CMS": "Content management",
    "Framework": "Frontend or app framework",
    "Hosting": "Host, CDN or edge network",
    "Analytics": "Traffic and product analytics",
    "Tag Manager": "Tag and script management",
    "Marketing": "Marketing automation, email and ads",
    "Support": "Live chat and helpdesk",
    "Payments": "Checkout and payment processing",
    "Reviews": "Ratings and user reviews",
    "Search": "On-site search and discovery",
    "Monitoring": "Error and performance monitoring",
    "Experimentation": "A/B testing and personalisation",
}

# name, category, [(signal_type, value, confidence)]
# `header` values are "name" or "name:value-substring".
FINGERPRINTS: list[dict] = [
    # -- Ecommerce -----------------------------------------------------------
    {"name": "Shopify", "category": "Ecommerce", "signals": [
        ("cookie", "_shopify_y", "confirmed"),
        ("cookie", "_shopify_s", "confirmed"),
        ("host", "cdn.shopify.com", "confirmed"),
        ("host", "monorail-edge.shopifysvc.com", "confirmed"),
        ("html", "Shopify.theme", "confirmed"),
        ("html", ".myshopify.com", "likely"),
        ("header", "x-shopify-stage", "confirmed"),
    ]},
    {"name": "Shopify Plus", "category": "Ecommerce", "signals": [
        ("html", "shopify-plus", "likely"),
        ("host", "shop.app", "likely"),
    ]},
    {"name": "WooCommerce", "category": "Ecommerce", "signals": [
        ("html", "woocommerce-page", "confirmed"),
        ("html", "/plugins/woocommerce/", "confirmed"),
        ("cookie", "woocommerce_cart_hash", "confirmed"),
        ("generator", "WooCommerce", "confirmed"),
    ]},
    {"name": "Magento", "category": "Ecommerce", "signals": [
        ("cookie", "X-Magento-Vary", "confirmed"),
        ("html", "/static/version", "likely"),
        ("html", "Magento_Ui/js", "confirmed"),
    ]},
    {"name": "BigCommerce", "category": "Ecommerce", "signals": [
        ("host", "cdn11.bigcommerce.com", "confirmed"),
        ("html", "bigcommerce.com/s-", "confirmed"),
    ]},
    {"name": "Salesforce Commerce Cloud", "category": "Ecommerce", "signals": [
        ("html", "/on/demandware.store/", "confirmed"),
        ("html", "demandware.static", "confirmed"),
    ]},
    {"name": "PrestaShop", "category": "Ecommerce", "signals": [
        ("generator", "PrestaShop", "confirmed"),
        ("html", "prestashop", "likely"),
    ]},
    {"name": "Wix Stores", "category": "Ecommerce", "signals": [
        ("html", "wixstores", "likely"),
    ]},

    # -- CMS -----------------------------------------------------------------
    {"name": "WordPress", "category": "CMS", "signals": [
        ("generator", "WordPress", "confirmed"),
        ("html", "/wp-content/", "confirmed"),
        ("html", "/wp-includes/", "confirmed"),
        ("html", "/wp-json/", "likely"),
    ]},
    {"name": "Wix", "category": "CMS", "signals": [
        ("generator", "Wix.com", "confirmed"),
        ("header", "server:Pepyaka", "confirmed"),
        ("cookie", "_wixCIDX", "confirmed"),
        ("host", "static.parastorage.com", "confirmed"),
    ]},
    {"name": "Squarespace", "category": "CMS", "signals": [
        ("header", "server:Squarespace", "confirmed"),
        ("cookie", "SS_MID", "confirmed"),
        ("host", "images.squarespace-cdn.com", "confirmed"),
        ("host", "assets.squarespace.com", "confirmed"),
    ]},
    {"name": "Webflow", "category": "CMS", "signals": [
        ("generator", "Webflow", "confirmed"),
        ("host", "assets.website-files.com", "confirmed"),
        ("host", "cdn.prod.website-files.com", "confirmed"),
    ]},
    {"name": "Drupal", "category": "CMS", "signals": [
        ("generator", "Drupal", "confirmed"),
        ("header", "x-drupal-cache", "confirmed"),
        ("html", "/sites/default/files/", "likely"),
    ]},
    {"name": "Ghost", "category": "CMS", "signals": [
        ("generator", "Ghost", "confirmed"),
        ("html", "/ghost/api/", "likely"),
    ]},
    {"name": "Contentful", "category": "CMS", "signals": [
        ("host", "images.ctfassets.net", "confirmed"),
        ("host", "videos.ctfassets.net", "confirmed"),
        ("host", "assets.ctfassets.net", "confirmed"),
    ]},
    {"name": "Sanity", "category": "CMS", "signals": [
        ("host", "cdn.sanity.io", "confirmed"),
    ]},
    {"name": "Storyblok", "category": "CMS", "signals": [
        ("host", "a.storyblok.com", "confirmed"),
    ]},
    {"name": "HubSpot CMS", "category": "CMS", "signals": [
        ("generator", "HubSpot", "confirmed"),
        ("host", "cdn2.hubspot.net", "confirmed"),
    ]},

    # -- Framework -----------------------------------------------------------
    {"name": "Next.js", "category": "Framework", "signals": [
        ("header", "x-powered-by:Next.js", "confirmed"),
        ("html", "__NEXT_DATA__", "confirmed"),
        ("html", "/_next/static/", "confirmed"),
        ("header", "x-nextjs-cache", "confirmed"),
    ]},
    {"name": "Nuxt", "category": "Framework", "signals": [
        ("html", "__NUXT__", "confirmed"),
        ("html", "/_nuxt/", "confirmed"),
    ]},
    {"name": "React", "category": "Framework", "signals": [
        ("html", "data-reactroot", "confirmed"),
        ("html", "__REACT_DEVTOOLS", "likely"),
    ]},
    {"name": "Vue.js", "category": "Framework", "signals": [
        ("html", "data-v-app", "likely"),
        ("html", "__VUE__", "likely"),
    ]},
    {"name": "Svelte / SvelteKit", "category": "Framework", "signals": [
        ("html", "__sveltekit", "confirmed"),
        ("html", "/_app/immutable/", "confirmed"),
    ]},
    {"name": "Angular", "category": "Framework", "signals": [
        ("html", "ng-version=", "confirmed"),
        ("html", "_nghost", "likely"),
    ]},
    {"name": "Astro", "category": "Framework", "signals": [
        ("generator", "Astro", "confirmed"),
        ("html", "astro-island", "confirmed"),
    ]},
    {"name": "Gatsby", "category": "Framework", "signals": [
        ("generator", "Gatsby", "confirmed"),
        ("html", "___gatsby", "confirmed"),
    ]},
    {"name": "Remix", "category": "Framework", "signals": [
        ("html", "__remixContext", "confirmed"),
    ]},
    {"name": "Ruby on Rails", "category": "Framework", "signals": [
        ("cookie", "_rails_session", "likely"),
        ("header", "x-powered-by:Phusion Passenger", "likely"),
        ("html", 'name="csrf-param" content="authenticity_token"', "confirmed"),
    ]},
    {"name": "Laravel", "category": "Framework", "signals": [
        ("cookie", "laravel_session", "confirmed"),
        ("cookie", "XSRF-TOKEN", "likely"),
    ]},
    {"name": "Django", "category": "Framework", "signals": [
        ("cookie", "csrftoken", "likely"),
        ("cookie", "django_language", "confirmed"),
    ]},
    {"name": "ASP.NET", "category": "Framework", "signals": [
        ("header", "x-aspnet-version", "confirmed"),
        ("header", "x-powered-by:ASP.NET", "confirmed"),
        ("cookie", "ASP.NET_SessionId", "confirmed"),
    ]},

    # -- Hosting / CDN -------------------------------------------------------
    {"name": "Cloudflare", "category": "Hosting", "signals": [
        ("header", "cf-ray", "confirmed"),
        ("header", "server:cloudflare", "confirmed"),
        ("cookie", "__cf_bm", "confirmed"),
    ]},
    {"name": "Vercel", "category": "Hosting", "signals": [
        ("header", "x-vercel-id", "confirmed"),
        ("header", "server:Vercel", "confirmed"),
    ]},
    {"name": "Netlify", "category": "Hosting", "signals": [
        ("header", "server:Netlify", "confirmed"),
        ("header", "x-nf-request-id", "confirmed"),
    ]},
    {"name": "Amazon CloudFront", "category": "Hosting", "signals": [
        ("header", "x-amz-cf-id", "confirmed"),
        ("header", "via:CloudFront", "confirmed"),
    ]},
    {"name": "Fastly", "category": "Hosting", "signals": [
        ("header", "x-served-by:cache-", "likely"),
        ("header", "x-fastly-request-id", "confirmed"),
    ]},
    {"name": "Akamai", "category": "Hosting", "signals": [
        ("header", "x-akamai-transformed", "confirmed"),
        ("header", "server:AkamaiGHost", "confirmed"),
    ]},
    {"name": "Nginx", "category": "Hosting", "signals": [
        ("header", "server:nginx", "confirmed"),
    ]},
    {"name": "Apache", "category": "Hosting", "signals": [
        ("header", "server:Apache", "confirmed"),
    ]},
    {"name": "GitHub Pages", "category": "Hosting", "signals": [
        ("header", "server:GitHub.com", "confirmed"),
    ]},

    # -- Analytics -----------------------------------------------------------
    {"name": "Google Analytics 4", "category": "Analytics", "signals": [
        ("host", "www.google-analytics.com", "confirmed"),
        ("html", "gtag('config', 'G-", "confirmed"),
        ("html", "googletagmanager.com/gtag/js", "confirmed"),
    ]},
    {"name": "Plausible", "category": "Analytics", "signals": [
        ("host", "plausible.io", "confirmed"),
    ]},
    {"name": "Fathom", "category": "Analytics", "signals": [
        ("host", "cdn.usefathom.com", "confirmed"),
    ]},
    {"name": "Matomo", "category": "Analytics", "signals": [
        ("html", "matomo.js", "confirmed"),
        ("html", "piwik.js", "likely"),
    ]},
    {"name": "Mixpanel", "category": "Analytics", "signals": [
        ("host", "cdn.mxpnl.com", "confirmed"),
        ("host", "api.mixpanel.com", "confirmed"),
    ]},
    {"name": "Amplitude", "category": "Analytics", "signals": [
        ("host", "cdn.amplitude.com", "confirmed"),
        ("host", "api2.amplitude.com", "confirmed"),
    ]},
    {"name": "Hotjar", "category": "Analytics", "signals": [
        ("host", "static.hotjar.com", "confirmed"),
        ("html", "hjSettings", "confirmed"),
    ]},
    {"name": "Segment", "category": "Analytics", "signals": [
        ("host", "cdn.segment.com", "confirmed"),
        ("html", "analytics.load(", "likely"),
    ]},
    {"name": "Microsoft Clarity", "category": "Analytics", "signals": [
        ("host", "www.clarity.ms", "confirmed"),
    ]},
    {"name": "PostHog", "category": "Analytics", "signals": [
        ("host", "app.posthog.com", "confirmed"),
        ("host", "us.i.posthog.com", "confirmed"),
    ]},

    # -- Tag managers --------------------------------------------------------
    {"name": "Google Tag Manager", "category": "Tag Manager", "signals": [
        ("host", "www.googletagmanager.com", "confirmed"),
        ("html", "GTM-", "likely"),
    ]},
    {"name": "Tealium", "category": "Tag Manager", "signals": [
        ("host", "tags.tiqcdn.com", "confirmed"),
    ]},

    # -- Marketing -----------------------------------------------------------
    {"name": "Meta Pixel", "category": "Marketing", "signals": [
        ("host", "connect.facebook.net", "confirmed"),
        ("html", "fbq('init'", "confirmed"),
    ]},
    {"name": "TikTok Pixel", "category": "Marketing", "signals": [
        ("host", "analytics.tiktok.com", "confirmed"),
    ]},
    {"name": "Klaviyo", "category": "Marketing", "signals": [
        ("host", "static.klaviyo.com", "confirmed"),
        ("host", "a.klaviyo.com", "confirmed"),
    ]},
    {"name": "Mailchimp", "category": "Marketing", "signals": [
        ("host", "chimpstatic.com", "confirmed"),
        ("host", "list-manage.com", "likely"),
    ]},
    {"name": "HubSpot", "category": "Marketing", "signals": [
        ("host", "js.hs-scripts.com", "confirmed"),
        ("host", "js.hs-analytics.net", "confirmed"),
        ("host", "js.hsforms.net", "confirmed"),
    ]},
    {"name": "Marketo", "category": "Marketing", "signals": [
        ("host", "munchkin.marketo.net", "confirmed"),
    ]},
    {"name": "Pardot", "category": "Marketing", "signals": [
        ("host", "pi.pardot.com", "confirmed"),
    ]},
    {"name": "Omnisend", "category": "Marketing", "signals": [
        ("host", "omnisnippet1.com", "confirmed"),
    ]},
    {"name": "Attentive", "category": "Marketing", "signals": [
        ("host", "cdn.attn.tv", "confirmed"),
    ]},
    {"name": "LinkedIn Insight Tag", "category": "Marketing", "signals": [
        ("host", "snap.licdn.com", "confirmed"),
    ]},

    # -- Support -------------------------------------------------------------
    {"name": "Intercom", "category": "Support", "signals": [
        ("host", "widget.intercom.io", "confirmed"),
        ("html", "intercomSettings", "confirmed"),
    ]},
    {"name": "Zendesk", "category": "Support", "signals": [
        ("host", "static.zdassets.com", "confirmed"),
        ("host", "ekr.zdassets.com", "confirmed"),
    ]},
    {"name": "Crisp", "category": "Support", "signals": [
        ("host", "client.crisp.chat", "confirmed"),
    ]},
    {"name": "Drift", "category": "Support", "signals": [
        ("host", "js.driftt.com", "confirmed"),
    ]},
    {"name": "Tidio", "category": "Support", "signals": [
        ("host", "code.tidio.co", "confirmed"),
    ]},
    {"name": "Gorgias", "category": "Support", "signals": [
        ("host", "config.gorgias.chat", "confirmed"),
    ]},
    {"name": "Freshdesk / Freshchat", "category": "Support", "signals": [
        ("host", "wchat.freshchat.com", "confirmed"),
    ]},

    # -- Payments ------------------------------------------------------------
    {"name": "Stripe", "category": "Payments", "signals": [
        ("host", "js.stripe.com", "confirmed"),
        ("host", "m.stripe.network", "confirmed"),
    ]},
    {"name": "PayPal", "category": "Payments", "signals": [
        ("host", "www.paypal.com", "likely"),
        ("host", "www.paypalobjects.com", "confirmed"),
    ]},
    {"name": "Klarna", "category": "Payments", "signals": [
        ("host", "x.klarnacdn.net", "confirmed"),
    ]},
    {"name": "Afterpay / Clearpay", "category": "Payments", "signals": [
        ("host", "static.afterpay.com", "confirmed"),
        ("host", "js.squarecdn.com/afterpay", "confirmed"),
    ]},
    {"name": "Adyen", "category": "Payments", "signals": [
        ("host", "checkoutshopper-live.adyen.com", "confirmed"),
    ]},

    # -- Reviews -------------------------------------------------------------
    {"name": "Trustpilot", "category": "Reviews", "signals": [
        ("host", "widget.trustpilot.com", "confirmed"),
    ]},
    {"name": "Yotpo", "category": "Reviews", "signals": [
        ("host", "staticw2.yotpo.com", "confirmed"),
        ("host", "cdn-widgetsrepository.yotpo.com", "confirmed"),
    ]},
    {"name": "Judge.me", "category": "Reviews", "signals": [
        ("host", "cdn.judge.me", "confirmed"),
    ]},
    {"name": "Okendo", "category": "Reviews", "signals": [
        ("host", "d3hw6dc1ow8pp2.cloudfront.net", "likely"),
        ("html", "okendo", "likely"),
    ]},

    # -- Search --------------------------------------------------------------
    {"name": "Algolia", "category": "Search", "signals": [
        ("host", "cdn.jsdelivr.net/npm/algoliasearch", "confirmed"),
        ("html", "algolia", "likely"),
        ("host", "insights.algolia.io", "confirmed"),
    ]},
    {"name": "Klevu", "category": "Search", "signals": [
        ("host", "js.klevu.com", "confirmed"),
    ]},
    {"name": "Searchanise", "category": "Search", "signals": [
        ("host", "searchserverapi.com", "confirmed"),
    ]},

    # -- Monitoring ----------------------------------------------------------
    {"name": "Sentry", "category": "Monitoring", "signals": [
        ("host", "browser.sentry-cdn.com", "confirmed"),
        ("html", "Sentry.init", "confirmed"),
    ]},
    {"name": "Datadog RUM", "category": "Monitoring", "signals": [
        ("host", "www.datadoghq-browser-agent.com", "confirmed"),
    ]},
    {"name": "New Relic", "category": "Monitoring", "signals": [
        ("html", "NREUM", "confirmed"),
        ("host", "js-agent.newrelic.com", "confirmed"),
    ]},

    # -- Experimentation -----------------------------------------------------
    {"name": "Optimizely", "category": "Experimentation", "signals": [
        ("host", "cdn.optimizely.com", "confirmed"),
    ]},
    {"name": "VWO", "category": "Experimentation", "signals": [
        ("host", "dev.visualwebsiteoptimizer.com", "confirmed"),
    ]},
    {"name": "Dynamic Yield", "category": "Experimentation", "signals": [
        ("host", "cdn.dynamicyield.com", "confirmed"),
    ]},
]
