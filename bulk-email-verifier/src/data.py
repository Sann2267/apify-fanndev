"""Static reference data for verification: free providers, role prefixes,
disposable domains and the typo-correction target list.

Everything here is deliberately embedded rather than downloaded at runtime.
A verifier that fetches its own wordlists gains a network dependency that can
fail mid-run and silently change every verdict -- the opposite of what a list
hygiene tool is bought for.
"""

from __future__ import annotations

# Consumer mailbox providers. Not a negative signal on its own: plenty of real
# customers use Gmail. It matters because a free-provider address never has a
# catch-all, so an SMTP 250 there is worth more than an SMTP 250 on a corporate
# domain that accepts everything.
FREE_PROVIDERS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "yahoo.co.in",
    "yahoo.co.jp", "yahoo.fr", "yahoo.de", "yahoo.es", "yahoo.it", "yahoo.ca",
    "ymail.com", "rocketmail.com", "hotmail.com", "hotmail.co.uk", "hotmail.fr",
    "hotmail.de", "hotmail.it", "hotmail.es", "outlook.com", "outlook.co.id",
    "live.com", "live.co.uk", "live.nl", "msn.com", "aol.com", "aim.com",
    "icloud.com", "me.com", "mac.com", "proton.me", "protonmail.com", "pm.me",
    "zoho.com", "zohomail.com", "gmx.com", "gmx.de", "gmx.net", "gmx.at",
    "web.de", "t-online.de", "freenet.de", "mail.com", "email.com", "usa.com",
    "yandex.ru", "yandex.com", "ya.ru", "mail.ru", "bk.ru", "inbox.ru",
    "list.ru", "rambler.ru", "qq.com", "163.com", "126.com", "sina.com",
    "sina.cn", "sohu.com", "naver.com", "daum.net", "hanmail.net",
    "rediffmail.com", "sify.com", "indiatimes.com", "bol.com.br", "uol.com.br",
    "terra.com.br", "ig.com.br", "globo.com", "libero.it", "virgilio.it",
    "alice.it", "tiscali.it", "orange.fr", "wanadoo.fr", "free.fr", "sfr.fr",
    "laposte.net", "bluewin.ch", "telenet.be", "skynet.be", "ziggo.nl",
    "xs4all.nl", "home.nl", "telia.com", "bredband.net", "online.no",
    "seznam.cz", "centrum.cz", "wp.pl", "o2.pl", "interia.pl", "onet.pl",
    "abv.bg", "mynet.com", "hotmail.com.tr", "bigpond.com", "optusnet.com.au",
    "xtra.co.nz", "shaw.ca", "sympatico.ca", "rogers.com", "comcast.net",
    "verizon.net", "att.net", "sbcglobal.net", "bellsouth.net", "cox.net",
    "charter.net", "earthlink.net", "juno.com", "netzero.net", "gmx.us",
    "fastmail.com", "hushmail.com", "tutanota.com", "tuta.io", "mailfence.com",
    "posteo.de", "runbox.com", "hey.com", "duck.com", "skiff.com",
}

# Mailboxes that belong to a function, not a person. They are deliverable but
# behave differently: higher spam-complaint rates, and most ESPs treat them as
# a compliance risk on cold campaigns. Reported separately from the verdict so
# the buyer decides rather than the actor deciding for them.
ROLE_PREFIXES = {
    "abuse", "admin", "administrator", "accounts", "accounting", "adm",
    "billing", "careers", "ceo", "cfo", "compliance", "contact", "cs",
    "customercare", "customerservice", "dev", "devnull", "enquiries",
    "enquiry", "everyone", "feedback", "finance", "ftp", "help", "helpdesk",
    "hello", "hi", "hostmaster", "hr", "info", "informacion", "inquiries",
    "inquiry", "investors", "it", "jobs", "legal", "list", "mail", "mailer",
    "mailerdaemon", "maildaemon", "marketing", "media", "newsletter", "no",
    "noc", "noreply", "no-reply", "notifications", "office", "operations",
    "order", "orders", "payments", "payroll", "postmaster", "press", "privacy",
    "purchasing", "recruitment", "registration", "reply", "root", "sales",
    "security", "service", "shop", "signup", "spam", "staff", "subscribe",
    "support", "sysadmin", "team", "tech", "testing", "unsubscribe", "usenet",
    "uucp", "web", "webmaster", "welcome", "www",
}

# Throwaway mailbox providers. This is a curated head of the distribution
# (the domains that actually show up in signup forms), not an attempt at the
# 100k-entry open-source lists -- those go stale in both directions and would
# dominate the image size. MX-host matching in dnsmx.py catches the long tail
# of aliases that point at the same handful of servers.
DISPOSABLE_DOMAINS = {
    "0-mail.com", "0clickemail.com", "10minutemail.com", "10minutemail.net",
    "10minutemail.co.uk", "20minutemail.com", "33mail.com", "3dmail.com",
    "guerrillamail.com", "guerrillamail.net", "guerrillamail.org",
    "guerrillamail.biz", "guerrillamail.de", "guerrillamailblock.com",
    "sharklasers.com", "grr.la", "spam4.me", "pokemail.net",
    "mailinator.com", "mailinator.net", "mailinator2.com", "notmailinator.com",
    "reallymymail.com", "sogetthis.com", "suremail.info", "veryrealemail.com",
    "binkmail.com", "bobmail.info", "chammy.info", "devnullmail.com",
    "letthemeatspam.com", "mailin8r.com", "mailnesia.com", "mailnull.com",
    "spamherelots.com", "spamhereplease.com", "thisisnotmyrealemail.com",
    "tempmail.com", "temp-mail.org", "temp-mail.io", "tempmail.net",
    "tempmailo.com", "tempail.com", "tempr.email", "tmpmail.org",
    "tmpmail.net", "tmpeml.com", "temporary-mail.net", "tempinbox.com",
    "throwawaymail.com", "trashmail.com", "trashmail.de", "trashmail.me",
    "trashmail.net", "trash-mail.com", "trash-mail.de", "wegwerfmail.de",
    "wegwerfmail.net", "wegwerfmail.org", "einrot.com", "fleckens.hu",
    "yopmail.com", "yopmail.fr", "yopmail.net", "cool.fr.nf", "jetable.fr.nf",
    "nospam.ze.tc", "nomail.xl.cx", "mega.zik.dj", "speed.1s.fr",
    "courriel.fr.nf", "moncourrier.fr.nf", "monemail.fr.nf", "monmail.fr.nf",
    "getnada.com", "nada.email", "getairmail.com", "inboxbear.com",
    "emailondeck.com", "emailfake.com", "fakemail.net", "fakeinbox.com",
    "fake-mail.ml", "mailcatch.com", "maildrop.cc", "mailsac.com",
    "mailhog.com", "inboxkitten.com", "harakirimail.com", "dispostable.com",
    "discard.email", "discardmail.com", "discardmail.de", "spambog.com",
    "spambog.de", "spambog.ru", "spamgourmet.com", "spamex.com",
    "mytemp.email", "mohmal.com", "mailtemp.info", "moakt.com", "moakt.co",
    "tempmailer.de", "tempemail.net", "tempemails.io", "instant-mail.de",
    "burnermail.io", "anonaddy.com", "anonaddy.me", "simplelogin.com",
    "simplelogin.io", "slmail.me", "relay.firefox.com", "mozmail.com",
    "1secmail.com", "1secmail.net", "1secmail.org", "esiix.com", "wwjmp.com",
    "xojxe.com", "yoggm.com", "dropmail.me", "10mail.org", "emltmp.com",
    "laste.ml", "zeroe.ml", "minuteinbox.com", "mailpoof.com", "mailbox.in.ua",
    "crazymailing.com", "cs.email", "internxt.com", "linshiyouxiang.net",
    "meltmail.com", "mintemail.com", "mailexpire.com", "kurzepost.de",
    "objectmail.com", "proxymail.eu", "rcpt.at", "trash2009.com",
    "mt2009.com", "mt2014.com", "mt2015.com", "thankyou2010.com",
    "tittbit.in", "venompen.com", "wuzup.net", "wuzupmail.net",
    "yapped.net", "zoemail.com", "zoemail.net", "zoemail.org",
    "emailsensei.com", "emailtemporanea.com", "emailtemporanea.net",
    "emailtemporar.ro", "emailthe.net", "emailtmp.com", "emailwarden.com",
    "emailxfer.com", "emeil.in", "emeil.ir", "emz.net", "enterto.com",
    "ephemail.net", "etranquil.com", "etranquil.net", "explodemail.com",
    "fansworldwide.de", "fantasymail.de", "fastacura.com", "fastchevy.com",
    "fastchrysler.com", "fastkawasaki.com", "fastmazda.com", "fastmitsubishi.com",
    "fastnissan.com", "fastsubaru.com", "fastsuzuki.com", "fasttoyota.com",
    "fastyamaha.com", "mailmetrash.com", "mailmoat.com", "mailquack.com",
    "mailscrap.com", "mailshell.com", "mailsiphon.com", "mailslapping.com",
    "mailzilla.com", "mailzilla.org", "nowmymail.com", "objectmail.org",
    "oneoffemail.com", "onewaymail.com", "owlpic.com", "pjjkp.com",
    "plexolan.de", "privacy.net", "punkass.com", "quickinbox.com",
    "rtrtr.com", "safetymail.info", "safersignup.de", "sneakemail.com",
    "snkmail.com", "sofort-mail.de", "spamavert.com", "spambox.us",
    "spamcero.com", "spamday.com", "spamfree24.com", "spamfree24.de",
    "spamfree24.org", "spaml.com", "spamobox.com", "spamspot.com",
    "squizzy.de", "tagyourself.com", "teewars.org", "teleworm.com",
    "teleworm.us", "thecloudindex.com", "thisisnotmyrealemail.com",
    "throwawayemailaddress.com", "tilien.com", "tmail.ws", "tmailinator.com",
    "toiea.com", "tradermail.info", "trbvm.com", "trialmail.de",
    "twinmail.de", "upliftnow.com", "uplipht.com", "venompen.net",
    "viditag.com", "viralplays.com", "vpn.st", "vsimcard.com", "vubby.com",
    "walala.org", "webm4il.info", "wh4f.org", "whyspam.me", "willhackforfood.biz",
    "willselfdestruct.com", "winemaven.info", "wronghead.com", "wwwnew.eu",
    "xagloo.com", "xemaps.com", "xents.com", "xmaily.com", "xoxy.net",
    "yep.it", "yogamaven.com", "yourdomain.com", "ypmail.webarnak.fr.eu.org",
    "zebins.com", "zebins.eu", "zetmail.com", "zippymail.info", "zomg.info",
}

# MX hostname fragments that give away a disposable provider even when the
# domain itself is one of their thousands of rotating aliases. This is the
# part a static domain list cannot do.
DISPOSABLE_MX_MARKERS = (
    "mailinator.com", "guerrillamail", "yopmail", "trashmail", "temp-mail",
    "tempmail", "1secmail", "dropmail", "mailsac", "maildrop", "moakt",
    "getnada", "inboxkitten", "emailondeck", "discardmail", "spamgourmet",
    "mytemp", "mohmal", "burnermail", "throwawaymail", "fakeinbox",
)

# Domains common enough that a near-miss is almost always a typo rather than a
# real company. Deliberately short: suggesting a "correction" for a legitimate
# small domain is worse than staying quiet.
TYPO_TARGETS = (
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "hotmail.com",
    "hotmail.co.uk", "outlook.com", "live.com", "msn.com", "aol.com",
    "icloud.com", "me.com", "proton.me", "protonmail.com", "zoho.com",
    "gmx.com", "gmx.de", "web.de", "mail.ru", "yandex.ru", "qq.com",
    "163.com", "naver.com", "comcast.net", "verizon.net", "att.net",
    "sbcglobal.net", "cox.net", "bellsouth.net", "charter.net", "me.com",
)
