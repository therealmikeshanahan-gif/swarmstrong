"""Turn companies into named people with verified direct emails.

Two stages, deliberately separate:

  1. enrich  — Apollo: company domain -> people matching our target titles.
  2. verify  — MillionVerifier: is this address actually deliverable?

Stage 2 is not optional. The OC-LA campaign's 0.4% bounce rate looked like a
quality signal and was in fact the tell that we had mailed role inboxes that
accept everything. Expect 3-5% bounce on a real named-contact list; a verified
list that comes back near 0% means the targeting slipped back to front desks.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

import requests

from .contacts import Contact

APOLLO_SEARCH = "https://api.apollo.io/api/v1/mixed_people/search"
MV_VERIFY = "https://api.millionverifier.com/api/v3/"

# Titles with budget or hands on the building.
TARGET_TITLES = [
    "property manager",
    "senior property manager",
    "commercial property manager",
    "assistant property manager",
    "regional property manager",
    "portfolio manager",
    "facilities manager",
    "facilities director",
    "director of facilities",
    "maintenance supervisor",
    "director of maintenance",
    "community association manager",
    "director of operations",
    "vice president asset management",
]


def domain_of(website: str) -> str:
    if not website:
        return ""
    host = urlparse(website if "//" in website else f"//{website}").netloc
    return host.lower().removeprefix("www.")


def apollo_people(domain: str, api_key: str | None = None, per_page: int = 10) -> list[dict]:
    """Find people at one domain matching our target titles."""
    api_key = api_key or os.environ.get("APOLLO_API_KEY")
    if not api_key:
        raise RuntimeError("APOLLO_API_KEY is not set")
    resp = requests.post(
        APOLLO_SEARCH,
        json={
            "q_organization_domains": domain,
            "person_titles": TARGET_TITLES,
            "page": 1,
            "per_page": per_page,
        },
        headers={"Content-Type": "application/json", "X-Api-Key": api_key},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("people", []) or []


def enrich_company(contact: Contact, **kwargs) -> list[Contact]:
    """Expand one company row into one row per named person found."""
    domain = domain_of(contact.website)
    if not domain:
        contact.rejected_reason = contact.rejected_reason or "no website to enrich"
        return [contact]

    people = apollo_people(domain, **kwargs)
    if not people:
        contact.rejected_reason = contact.rejected_reason or "no named contact found"
        return [contact]

    out = []
    for person in people:
        name = " ".join(filter(None, [person.get("first_name"), person.get("last_name")]))
        out.append(Contact(
            company=contact.company,
            tier=contact.tier,
            city=contact.city,
            county=contact.county,
            contact_name=name,
            title=person.get("title", "") or "",
            email=person.get("email", "") or "",
            # Prefer a direct line; fall back to the company's main number.
            phone=person.get("sanitized_phone") or contact.phone,
            website=contact.website,
            source=f"{contact.source}+apollo",
        ))
    return out


def verify_email(email: str, api_key: str | None = None) -> bool:
    """True only for addresses MillionVerifier calls deliverable."""
    api_key = api_key or os.environ.get("MILLIONVERIFIER_API_KEY")
    if not api_key:
        raise RuntimeError("MILLIONVERIFIER_API_KEY is not set")
    resp = requests.get(MV_VERIFY, params={"api": api_key, "email": email}, timeout=30)
    resp.raise_for_status()
    return resp.json().get("result") == "ok"


def verify_all(contacts: list[Contact], **kwargs) -> list[Contact]:
    for c in contacts:
        if not c.email or c.rejected_reason:
            continue
        try:
            c.email_verified = verify_email(c.email, **kwargs)
            if not c.email_verified:
                c.rejected_reason = "failed verification"
        except Exception as exc:  # keep going; one bad call must not kill a run
            c.notes = (c.notes + f" verify-error:{exc}").strip()
    return contacts
