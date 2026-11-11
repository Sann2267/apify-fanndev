"""SMTP mailbox probe: the only part of verification that talks to a mail server.

The conversation stops at RCPT TO and never sends DATA, so no mail is
generated for the address being checked. That is the standard list-hygiene
handshake, and it is also why this file is written defensively: greylisting,
rate limits and catch-all domains all return "yes" or "maybe" for addresses
that do not exist, and reporting those as deliverable is the failure mode that
makes a verifier worthless.

Port 25 egress is blocked by default on most cloud providers. Every entry
point here degrades to a reported "unknown" instead of raising, and
`probe_egress()` tells the run which world it is in.
"""

from __future__ import annotations

import asyncio
import base64
import random
import string
from urllib.parse import unquote, urlparse

# smtpDeliverable tri-state: True (accepted), False (rejected), None (no answer
# we are willing to act on). Anything ambiguous must land on None.
ACCEPT_CODES = {250, 251}
REJECT_CODES = {550, 551, 553, 554}
# 450/451/452 = greylisting or throttling, 421 = service closing, 552 = mailbox
# full. All of them mean "ask again later", none of them mean "does not exist".
DEFER_CODES = {421, 450, 451, 452, 552}

# The one-off egress probe never needs the full per-step budget: a host that
# allows port 25 answers in well under this, and one that blocks it never will.
PROBE_TIMEOUT_CAP = 8.0


def _random_local(length: int = 16) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


async def open_tunnel(proxy_url: str, host: str, port: int, timeout: float):
    """Open a TCP tunnel to host:port through an HTTP proxy via CONNECT.

    The platform blocks outbound port 25 directly, so this is the only route
    to a mail server from a hosted run -- and only if the proxy itself allows
    CONNECT to a non-443 port, which most do not. A refusal comes back as a
    plain HTTP status line, which is why the response is parsed rather than
    assumed.
    """
    parsed = urlparse(proxy_url)
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(parsed.hostname, parsed.port or 8000), timeout=timeout
    )
    crlf = "\r\n"
    lines = [f"CONNECT {host}:{port} HTTP/1.1", f"Host: {host}:{port}"]
    if parsed.username:
        credentials = f"{unquote(parsed.username)}:{unquote(parsed.password or empty)}"
        token = base64.b64encode(credentials.encode()).decode()
        lines.append(f"Proxy-Authorization: Basic {token}")
    writer.write((crlf.join(lines) + crlf + crlf).encode())
    await asyncio.wait_for(writer.drain(), timeout=timeout)

    status = await asyncio.wait_for(reader.readline(), timeout=timeout)
    status_text = status.decode("utf-8", errors="replace").strip()
    # Drain the remaining proxy headers so the stream starts at the SMTP banner.
    while True:
        line = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if line in (crlf.encode(), b"\n", b""):
            break
    if " 200" not in status_text:
        writer.close()
        raise ConnectionError(f"proxy refused CONNECT: {status_text[:120]}")
    return reader, writer


class SmtpSession:
    """One TCP conversation with one MX host."""

    def __init__(self, host: str, port: int, timeout: float, helo: str, mail_from: str,
                 proxy_url: str | None = None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.helo = helo
        self.mail_from = mail_from
        self.proxy_url = proxy_url
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None

    async def __aenter__(self) -> "SmtpSession":
        if self.proxy_url:
            self.reader, self.writer = await open_tunnel(
                self.proxy_url, self.host, self.port, self.timeout
            )
        else:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=self.timeout
            )
        return self

    async def __aexit__(self, *_exc) -> None:
        try:
            if self.writer is not None:
                try:
                    await self._command("QUIT")
                except Exception:
                    pass
                self.writer.close()
                await asyncio.wait_for(self.writer.wait_closed(), timeout=5)
        except Exception:
            pass

    async def _read_reply(self) -> tuple[int, str]:
        """Read one SMTP reply, following multi-line continuations."""
        assert self.reader is not None
        lines: list[str] = []
        while True:
            raw = await asyncio.wait_for(self.reader.readline(), timeout=self.timeout)
            if not raw:
                raise ConnectionError("connection closed by server")
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            lines.append(line)
            # "250-" continues, "250 " terminates.
            if len(line) >= 4 and line[3] == "-":
                continue
            break
        last = lines[-1]
        try:
            code = int(last[:3])
        except ValueError as exc:
            raise ConnectionError(f"unparseable reply: {last[:80]}") from exc
        return code, " | ".join(lines)[:400]

    async def _command(self, text: str) -> tuple[int, str]:
        assert self.writer is not None
        self.writer.write((text + "\r\n").encode("utf-8"))
        await asyncio.wait_for(self.writer.drain(), timeout=self.timeout)
        return await self._read_reply()

    async def banner(self) -> tuple[int, str]:
        return await self._read_reply()

    async def ehlo(self) -> tuple[int, str]:
        code, message = await self._command(f"EHLO {self.helo}")
        if code >= 400:
            # Servers that predate ESMTP, and a few appliances, only speak HELO.
            code, message = await self._command(f"HELO {self.helo}")
        return code, message

    async def mail_from_cmd(self) -> tuple[int, str]:
        return await self._command(f"MAIL FROM:<{self.mail_from}>")

    async def rcpt_to(self, address: str) -> tuple[int, str]:
        return await self._command(f"RCPT TO:<{address}>")


class SmtpProbe:
    def __init__(self, timeout: float = 12.0, helo: str = "mail.example.com",
                 mail_from: str = "verify@example.com", detect_catch_all: bool = True,
                 port: int = 25, log=None, proxy_url: str | None = None):
        self.proxy_url = proxy_url
        self.route = "proxy-connect" if proxy_url else "direct"
        self.timeout = timeout
        self.helo = helo
        self.mail_from = mail_from
        self.detect_catch_all = detect_catch_all
        self.port = port
        self.log = log
        self.egress_ok: bool | None = None
        self.egress_detail: str = "not tested"
        self._catch_all: dict[str, bool | None] = {}
        self._domain_locks: dict[str, asyncio.Lock] = {}
        self.attempted = 0
        self.answered = 0

    async def probe_egress(self, host: str = "gmail-smtp-in.l.google.com") -> bool:
        """Can this runtime open port 25 at all?

        Run once before the list. If it fails, every SMTP check is skipped
        rather than each address paying a full timeout to learn the same thing.

        Measured on the Apify platform 2026-09-22: blocked both directly and
        through an Apify proxy CONNECT tunnel. The probe is capped below the
        per-step SMTP timeout so a hosted run loses seconds to that fact, not
        the full budget.
        """
        probe_timeout = min(self.timeout, PROBE_TIMEOUT_CAP)
        try:
            if self.proxy_url:
                reader, writer = await open_tunnel(self.proxy_url, host, self.port, probe_timeout)
            else:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, self.port), timeout=probe_timeout
                )
            try:
                raw = await asyncio.wait_for(reader.readline(), timeout=probe_timeout)
                banner = raw.decode("utf-8", errors="replace").strip()
            finally:
                writer.close()
                try:
                    await asyncio.wait_for(writer.wait_closed(), timeout=5)
                except Exception:
                    pass
            self.egress_ok = True
            self.egress_detail = banner[:200] or "connected, no banner"
        except Exception as exc:
            self.egress_ok = False
            self.egress_detail = f"{type(exc).__name__}: {exc}"[:200]
        if self.log:
            state = "OPEN" if self.egress_ok else "BLOCKED"
            self.log.info(
                f"SMTP port {self.port} egress via {self.route}: {state} -- {self.egress_detail}"
            )
        return bool(self.egress_ok)

    @staticmethod
    def _blank(reason: str) -> dict:
        return {
            "smtpChecked": False, "smtpDeliverable": None, "smtpCode": None,
            "smtpMessage": None, "smtpStage": reason, "isCatchAll": None,
        }

    async def check(self, address: str, domain: str, mx_host: str) -> dict:
        if self.egress_ok is False:
            return self._blank("skipped_port_blocked")
        if not mx_host:
            return self._blank("skipped_no_mx")

        # One conversation at a time per domain. Mail servers answer honestly
        # to a slow prober and start rejecting everything to a fast one -- and
        # a server that rate-limits us returns 550s that look exactly like
        # "mailbox does not exist".
        lock = self._domain_locks.setdefault(domain, asyncio.Lock())
        async with lock:
            self.attempted += 1
            try:
                async with SmtpSession(mx_host, self.port, self.timeout,
                                       self.helo, self.mail_from) as session:
                    code, message = await session.banner()
                    if code != 220:
                        return {"smtpChecked": True, "smtpDeliverable": None,
                                "smtpCode": code, "smtpMessage": message,
                                "smtpStage": "banner", "isCatchAll": None}

                    code, message = await session.ehlo()
                    if code >= 400:
                        return {"smtpChecked": True, "smtpDeliverable": None,
                                "smtpCode": code, "smtpMessage": message,
                                "smtpStage": "ehlo", "isCatchAll": None}

                    code, message = await session.mail_from_cmd()
                    if code >= 400:
                        return {"smtpChecked": True, "smtpDeliverable": None,
                                "smtpCode": code, "smtpMessage": message,
                                "smtpStage": "mail_from", "isCatchAll": None}

                    code, message = await session.rcpt_to(address)
                    self.answered += 1
                    deliverable: bool | None
                    if code in ACCEPT_CODES:
                        deliverable = True
                    elif code in DEFER_CODES:
                        deliverable = None
                    elif code in REJECT_CODES or 500 <= code < 600:
                        deliverable = False
                    else:
                        deliverable = None

                    catch_all = self._catch_all.get(domain)
                    # Only worth asking when the address was accepted: on a
                    # rejection we already know the server discriminates.
                    if (self.detect_catch_all and deliverable is True
                            and catch_all is None):
                        probe_address = f"{_random_local()}@{domain}"
                        try:
                            probe_code, _ = await session.rcpt_to(probe_address)
                            catch_all = probe_code in ACCEPT_CODES
                        except Exception:
                            catch_all = None
                        self._catch_all[domain] = catch_all

                    return {"smtpChecked": True, "smtpDeliverable": deliverable,
                            "smtpCode": code, "smtpMessage": message,
                            "smtpStage": "rcpt_to", "isCatchAll": catch_all}

            except asyncio.TimeoutError:
                return {"smtpChecked": True, "smtpDeliverable": None, "smtpCode": None,
                        "smtpMessage": "timeout", "smtpStage": "timeout", "isCatchAll": None}
            except Exception as exc:
                return {"smtpChecked": True, "smtpDeliverable": None, "smtpCode": None,
                        "smtpMessage": f"{type(exc).__name__}: {exc}"[:200],
                        "smtpStage": "connect_failed", "isCatchAll": None}
