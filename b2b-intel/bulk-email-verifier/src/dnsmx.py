"""MX / A lookups with a per-domain cache.

A 50k-row list is usually a few thousand distinct domains, so caching per
domain is the difference between 50k lookups and 3k. The cache lives for one
run only -- DNS answers are not stable enough to carry across runs, and a
stale MX is exactly the kind of quiet wrongness this actor exists to remove.
"""

from __future__ import annotations

import asyncio

import dns.asyncresolver
import dns.exception
import dns.rdatatype
import dns.resolver

from src.data import DISPOSABLE_MX_MARKERS

# ok         -> at least one MX (or a usable A/AAAA fallback)
# no_mx      -> the domain resolves but accepts no mail
# nxdomain   -> the domain does not exist at all
# dns_timeout/dns_error -> our lookup failed; says nothing about the address
DOMAIN_OK = "ok"
DOMAIN_NO_MX = "no_mx"
DOMAIN_NXDOMAIN = "nxdomain"
DOMAIN_TIMEOUT = "dns_timeout"
DOMAIN_ERROR = "dns_error"


class MxResolver:
    def __init__(self, timeout: float = 8.0, nameservers: list[str] | None = None):
        self._resolver = dns.asyncresolver.Resolver(configure=True)
        self._resolver.timeout = timeout
        self._resolver.lifetime = timeout
        if nameservers:
            self._resolver.nameservers = nameservers
        self._cache: dict[str, dict] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    @property
    def cached_domains(self) -> int:
        return len(self._cache)

    async def lookup(self, domain: str) -> dict:
        if domain in self._cache:
            return self._cache[domain]
        # One in-flight lookup per domain: a list sorted by domain would
        # otherwise fire hundreds of identical queries before the first lands.
        lock = self._locks.setdefault(domain, asyncio.Lock())
        async with lock:
            if domain in self._cache:
                return self._cache[domain]
            result = await self._lookup_uncached(domain)
            self._cache[domain] = result
            return result

    async def _lookup_uncached(self, domain: str) -> dict:
        try:
            answer = await self._resolver.resolve(domain, dns.rdatatype.MX)
            records = sorted(
                (
                    {
                        "host": str(rdata.exchange).rstrip(".").lower(),
                        "preference": int(rdata.preference),
                    }
                    for rdata in answer
                ),
                key=lambda item: item["preference"],
            )
            # "." as the sole exchange is RFC 7505's explicit "this domain
            # sends no mail" null MX. Treating it as a host would produce a
            # connection error and a misleading "unknown".
            records = [r for r in records if r["host"] not in ("", ".")]
            if records:
                return self._ok(records)
            return {"domainStatus": DOMAIN_NO_MX, "mxRecords": [], "mxHost": None,
                    "disposableMx": False, "dnsError": "null_mx"}
        except dns.resolver.NXDOMAIN:
            return {"domainStatus": DOMAIN_NXDOMAIN, "mxRecords": [], "mxHost": None,
                    "disposableMx": False, "dnsError": "nxdomain"}
        except dns.resolver.NoAnswer:
            return await self._a_fallback(domain)
        except (dns.resolver.LifetimeTimeout, dns.exception.Timeout):
            return {"domainStatus": DOMAIN_TIMEOUT, "mxRecords": [], "mxHost": None,
                    "disposableMx": False, "dnsError": "timeout"}
        except dns.resolver.NoNameservers as exc:
            return {"domainStatus": DOMAIN_ERROR, "mxRecords": [], "mxHost": None,
                    "disposableMx": False, "dnsError": f"no_nameservers: {exc}"[:200]}
        except Exception as exc:
            return {"domainStatus": DOMAIN_ERROR, "mxRecords": [], "mxHost": None,
                    "disposableMx": False, "dnsError": f"{type(exc).__name__}: {exc}"[:200]}

    async def _a_fallback(self, domain: str) -> dict:
        """No MX record, but RFC 5321 says an A record is an implicit MX.

        Small self-hosted domains rely on this, so skipping it would mark
        genuine mailboxes undeliverable.
        """
        for rdtype in (dns.rdatatype.A, dns.rdatatype.AAAA):
            try:
                await self._resolver.resolve(domain, rdtype)
            except Exception:
                continue
            return self._ok([{"host": domain, "preference": 0}], implicit=True)
        return {"domainStatus": DOMAIN_NO_MX, "mxRecords": [], "mxHost": None,
                "disposableMx": False, "dnsError": "no_mx_no_a"}

    @staticmethod
    def _ok(records: list[dict], implicit: bool = False) -> dict:
        hosts = " ".join(r["host"] for r in records)
        return {
            "domainStatus": DOMAIN_OK,
            "mxRecords": records,
            "mxHost": records[0]["host"],
            "implicitMx": implicit,
            "disposableMx": any(marker in hosts for marker in DISPOSABLE_MX_MARKERS),
            "dnsError": None,
        }
