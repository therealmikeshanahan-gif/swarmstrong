"""Decide whether an inbound message is really a prospect reply.

Why this exists
---------------
On 2026-10-12 the reply watcher fired six "NEW LEAD REPLY" alerts for the
OC-LA Property Managers campaign. Every one of them was our own step-4
follow-up, sent FROM one of our mailboxes TO the prospect:

    From: clark@teamarmoredglass.com
    To:   info@dukepm.com
    Subject: Re: Who handles entry glass maintenance?
    "Last follow-up from me... CA Contractor License #997737"

Because the sequence sends step 4 in-thread, the subject carried "Re:" and the
watcher took it for an inbound reply. It then classified our own copy as
`negative_or_no_current_need` and asked a human to answer it.

Net effect: the campaign's true reply count was 0 of 259, but the dashboard
read "3 replies", which made a total failure look like a working campaign.

The rule that fixes it is `classify()` step 1: if the From address is one of
ours, it is outbound and we never alert. Everything else here exists so the
alert can say *which kind* of reply it is, because an out-of-office and a
human asking for a price should not page anyone the same way.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from email import message_from_bytes, message_from_string
from email.message import Message
from typing import Literal, Mapping

from .identity import Identities, extract_addresses

Kind = Literal["outbound_self", "bounce", "autoreply", "human_reply"]

# --- bounce / delivery-status signals ---------------------------------------
_BOUNCE_SENDERS = (
    "mailer-daemon",
    "postmaster",
    "no-reply@",
    "noreply@",
)
_BOUNCE_SUBJECTS = (
    "undeliverable",
    "undelivered mail",
    "delivery status notification",
    "returned mail",
    "mail delivery failed",
    "address not found",
    "delivery incomplete",
)
_BOUNCE_CONTENT_TYPES = ("multipart/report", "message/delivery-status")

# --- autoresponder signals --------------------------------------------------
_AUTOREPLY_SUBJECTS = (
    "out of office",
    "automatic reply",
    "auto-reply",
    "autoreply",
    "away from",
    "on vacation",
    "maternity leave",
    "no longer with",
)
_AUTOREPLY_BODY = (
    "out of the office",
    "out of office",
    "automatic reply",
    "i am currently away",
    "currently out of",
    "will be out until",
    "no longer with the company",
    "no longer employed",
    "thank you for your email, i am",
    "this is an automated",
    "do not reply to this message",
)
_AUTOREPLY_HEADERS = {
    "auto-submitted": lambda v: v.lower().startswith("auto-"),
    "x-autoreply": lambda v: True,
    "x-autorespond": lambda v: True,
    "x-auto-response-suppress": lambda v: True,
    "precedence": lambda v: v.lower() in {"bulk", "auto_reply", "junk", "list"},
}

_OPT_OUT_PATTERNS = (
    r"\bno\s*thanks\b",
    r"\bunsubscribe\b",
    r"\bremove me\b",
    r"\btake me off\b",
    r"\bstop (?:emailing|contacting)\b",
    r"\bdo not (?:contact|email)\b",
    r"\bopt[- ]?out\b",
)


@dataclass(frozen=True)
class Verdict:
    kind: Kind
    alert: bool
    reason: str
    responder: str | None = None
    opt_out: bool = False

    @property
    def is_real_reply(self) -> bool:
        """True only for mail a human at the prospect actually wrote."""
        return self.kind == "human_reply"


def _header(headers: Mapping[str, str], name: str) -> str:
    """Case-insensitive header lookup that tolerates missing keys."""
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value or ""
    return ""


def _contains_any(haystack: str, needles) -> bool:
    low = haystack.lower()
    return any(n in low for n in needles)


def detect_opt_out(body: str) -> bool:
    """Opt-out wins over everything. We honor it even inside an autoresponder."""
    low = (body or "").lower()
    return any(re.search(p, low) for p in _OPT_OUT_PATTERNS)


def classify(
    headers: Mapping[str, str],
    body: str,
    identities: Identities,
) -> Verdict:
    """Classify one message. Order matters — step 1 is the Oct 12 fix."""
    from_hdr = _header(headers, "From")
    to_hdr = _header(headers, "To")
    subject = _header(headers, "Subject")
    content_type = _header(headers, "Content-Type")
    body = body or ""

    senders = extract_addresses(from_hdr)
    responder = senders[0] if senders else None

    # 1. OUR OWN MAIL. Never alert, whatever the subject says.
    if identities.owns_any(from_hdr):
        return Verdict(
            "outbound_self",
            alert=False,
            reason=f"From {responder} is one of our sending identities",
            responder=responder,
        )

    # 1b. Backstop: a forward can strip the real From. If the body is clearly
    # our copy and the recipient is not us, it is still our mail.
    if identities.body_looks_like_ours(body) and not identities.owns_any(to_hdr):
        return Verdict(
            "outbound_self",
            alert=False,
            reason="body matches our own sequence copy",
            responder=responder,
        )

    # 2. Bounces. Not a reply; the address needs retiring.
    if (
        _contains_any(from_hdr, _BOUNCE_SENDERS)
        or _contains_any(subject, _BOUNCE_SUBJECTS)
        or _contains_any(content_type, _BOUNCE_CONTENT_TYPES)
    ):
        return Verdict(
            "bounce",
            alert=False,
            reason="delivery status notification",
            responder=responder,
        )

    opt_out = detect_opt_out(body)

    # 3. Autoresponders. Logged, not paged.
    for name, test in _AUTOREPLY_HEADERS.items():
        value = _header(headers, name)
        if value and test(value):
            return Verdict(
                "autoreply",
                alert=False,
                reason=f"{name}: {value}",
                responder=responder,
                opt_out=opt_out,
            )
    if _contains_any(subject, _AUTOREPLY_SUBJECTS) or _contains_any(body, _AUTOREPLY_BODY):
        return Verdict(
            "autoreply",
            alert=False,
            reason="out-of-office / automated wording",
            responder=responder,
            opt_out=opt_out,
        )

    # 4. A human at the prospect wrote this. Page someone.
    return Verdict(
        "human_reply",
        alert=True,
        reason="human reply — answer within 1 business hour",
        responder=responder,
        opt_out=opt_out,
    )


def classify_message(msg: Message, identities: Identities) -> Verdict:
    """Classify a parsed email.message.Message."""
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    parts.append(payload.decode(part.get_content_charset() or "utf-8", "replace"))
        body = "\n".join(parts)
    else:
        payload = msg.get_payload(decode=True)
        body = (
            payload.decode(msg.get_content_charset() or "utf-8", "replace")
            if payload
            else str(msg.get_payload())
        )
    return classify(dict(msg.items()), body, identities)


def classify_raw(raw: bytes | str, identities: Identities) -> Verdict:
    """Classify a raw RFC822 message — the drop-in entry point for the watcher."""
    msg = message_from_bytes(raw) if isinstance(raw, bytes) else message_from_string(raw)
    return classify_message(msg, identities)
