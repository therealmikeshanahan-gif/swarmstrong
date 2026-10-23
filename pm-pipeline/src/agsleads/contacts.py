"""One contact record, and the rules that decide whether it is worth mailing.

Phone is a column on this record, not a second pipeline. The email list and the
call list are two views of the same rows, so a contact can never drift between
them and Julia and the sequence are always working the same data.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Tiers that must never receive a role-inbox send. Tier E is often a one-person
# shop where info@ is the owner, so it is flagged rather than dropped.
STRICT_TIERS = frozenset({"A", "B", "C", "D"})

_PHONE_RE = re.compile(r"\D+")
_SUFFIXES = (
    "inc", "inc.", "llc", "l.l.c.", "lp", "l.p.", "llp", "corp", "corp.",
    "corporation", "company", "co", "co.", "ltd", "the", "group", "amo",
)


def load_role_inboxes(path: str | Path) -> frozenset[str]:
    lines = Path(path).read_text().splitlines()
    return frozenset(
        line.strip().lower()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    )


def normalize_phone(raw: str | None) -> str | None:
    """Return a 10-digit US number as (XXX) XXX-XXXX, or None if unusable."""
    if not raw:
        return None
    digits = _PHONE_RE.sub("", raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return None
    if digits[0] in "01" or digits[3] in "01":  # invalid NANP area/exchange
        return None
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def normalize_company(name: str | None) -> str:
    """Collapse a company name to a dedupe key.

    "The Example Group, AMO" and "Example Group Inc." both become "example".
    """
    if not name:
        return ""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s]", " ", text.lower())
    words = [w for w in text.split() if w and w not in _SUFFIXES]
    return " ".join(words)


def email_local_part(email: str | None) -> str:
    if not email or "@" not in email:
        return ""
    return email.split("@", 1)[0].strip().lower()


def is_role_inbox(email: str | None, role_inboxes: frozenset[str]) -> bool:
    """True if the address is a front desk rather than a person.

    Catches three shapes of decoration:
      info@            exact
      front-desk@      separators removed  -> "frontdesk"
      info.la@         first segment       -> "info"
      leasing2@        trailing digits off -> "leasing"

    Short codes (ap, ar, hr) match exactly only, so a person whose local part
    is their initials — hr.patel@ — is not mistaken for a mailbox.
    """
    local = email_local_part(email)
    if not local:
        return False
    if local in role_inboxes:
        return True

    collapsed = re.sub(r"\d+$", "", re.sub(r"[^a-z0-9]", "", local))
    if collapsed in role_inboxes:
        return True

    stem = re.sub(r"\d+$", "", re.split(r"[._\-+]", local)[0])
    return len(stem) > 2 and stem in role_inboxes


@dataclass
class Contact:
    company: str
    tier: str
    city: str = ""
    county: str = ""
    contact_name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    website: str = ""
    source: str = ""
    # set by the pipeline
    email_verified: bool = False
    rejected_reason: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        self.email = (self.email or "").strip().lower()
        self.phone = normalize_phone(self.phone) or ""
        self.company = (self.company or "").strip()
        self.tier = (self.tier or "").strip().upper()

    @property
    def company_key(self) -> str:
        return normalize_company(self.company)

    @property
    def has_person(self) -> bool:
        return bool(self.contact_name.strip())

    def screen(self, role_inboxes: frozenset[str]) -> "Contact":
        """Apply the list-building rules. Sets rejected_reason when unmailable."""
        if not self.email:
            self.rejected_reason = "no email"
            return self
        if is_role_inbox(self.email, role_inboxes):
            if self.tier in STRICT_TIERS:
                self.rejected_reason = "role inbox"
            else:
                self.notes = (self.notes + " role-inbox-allowed-tier-E").strip()
            return self
        return self

    @property
    def mailable(self) -> bool:
        return bool(self.email) and not self.rejected_reason and self.email_verified

    @property
    def callable_(self) -> bool:
        return bool(self.phone)

    def as_row(self) -> dict:
        return asdict(self)


@dataclass
class DedupeResult:
    kept: list[Contact] = field(default_factory=list)
    dropped: list[Contact] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return f"{len(self.kept)} kept, {len(self.dropped)} duplicates dropped"


def dedupe(contacts: list[Contact], already_contacted: frozenset[str] = frozenset()) -> DedupeResult:
    """Drop duplicates and anyone a prior campaign already touched.

    `already_contacted` is the union of every address loaded into Instantly to
    date. Pass it in so a contact can never be mailed by two campaigns at once.
    """
    result = DedupeResult()
    seen_emails: set[str] = set()
    seen_person: set[tuple[str, str]] = set()

    for c in contacts:
        if c.email and c.email in already_contacted:
            c.rejected_reason = "already in a prior campaign"
            result.dropped.append(c)
            continue
        if c.email:
            if c.email in seen_emails:
                c.rejected_reason = "duplicate email"
                result.dropped.append(c)
                continue
            seen_emails.add(c.email)
        else:
            # No email: dedupe on company + person so the call list stays clean.
            key = (c.company_key, c.contact_name.strip().lower())
            if key in seen_person:
                c.rejected_reason = "duplicate company/person"
                result.dropped.append(c)
                continue
            seen_person.add(key)
        result.kept.append(c)

    return result
