"""Write the master table and the two working views.

contacts_master.csv — every row, including rejects, with the reason. Audit trail.
email_list.csv      — verified, non-role, named-person addresses. Loads into Instantly.
call_list.csv       — anything with a phone, Julia's dialing order.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .contacts import Contact

MASTER_FIELDS = [
    "tier", "company", "contact_name", "title", "email", "phone",
    "city", "county", "website", "source", "email_verified",
    "rejected_reason", "notes",
]

EMAIL_FIELDS = [
    "email", "first_name", "last_name", "title", "company",
    "phone", "city", "county", "tier",
]

CALL_FIELDS = [
    "tier", "company", "contact_name", "title", "phone",
    "city", "county", "email", "has_email", "notes",
]


def _split_name(full: str) -> tuple[str, str]:
    parts = (full or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _write(path: Path, fields: list[str], rows: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def write_master(contacts: list[Contact], out_dir: str | Path) -> int:
    return _write(Path(out_dir) / "contacts_master.csv", MASTER_FIELDS,
                  [c.as_row() for c in contacts])


def write_email_list(contacts: list[Contact], out_dir: str | Path) -> int:
    rows = []
    for c in sorted((x for x in contacts if x.mailable),
                    key=lambda x: (x.tier, x.county, x.company)):
        first, last = _split_name(c.contact_name)
        rows.append({
            "email": c.email, "first_name": first, "last_name": last,
            "title": c.title, "company": c.company, "phone": c.phone,
            "city": c.city, "county": c.county, "tier": c.tier,
        })
    return _write(Path(out_dir) / "email_list.csv", EMAIL_FIELDS, rows)


def write_call_list(contacts: list[Contact], out_dir: str | Path) -> int:
    """Phone-reachable rows. Contacts with no usable email come first —
    those are the ones the sequence can never reach, so a call is the only way in."""
    rows = []
    callable_rows = [c for c in contacts if c.callable_ and c.rejected_reason != "duplicate email"]
    for c in sorted(callable_rows, key=lambda x: (bool(x.mailable), x.tier, x.county, x.company)):
        rows.append({
            "tier": c.tier, "company": c.company, "contact_name": c.contact_name,
            "title": c.title, "phone": c.phone, "city": c.city,
            "county": c.county, "email": c.email,
            "has_email": "yes" if c.mailable else "no",
            "notes": c.notes,
        })
    return _write(Path(out_dir) / "call_list.csv", CALL_FIELDS, rows)


def write_all(contacts: list[Contact], out_dir: str | Path) -> dict[str, int]:
    return {
        "contacts_master.csv": write_master(contacts, out_dir),
        "email_list.csv": write_email_list(contacts, out_dir),
        "call_list.csv": write_call_list(contacts, out_dir),
    }
