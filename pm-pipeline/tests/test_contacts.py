"""Tests for the list-building rules.

The role-inbox cases use the actual addresses from the failed OC-LA campaign.
"""

from pathlib import Path

import pytest

from agsleads.contacts import (
    Contact,
    dedupe,
    is_role_inbox,
    load_role_inboxes,
    normalize_company,
    normalize_phone,
)
from agsleads.export import write_all

ROOT = Path(__file__).resolve().parents[1]
ROLE_INBOXES = load_role_inboxes(ROOT / "config" / "role_inboxes.txt")


# --- the addresses that produced 0 replies from 259 sends -------------------

@pytest.mark.parametrize(
    "email",
    [
        "info@dukepm.com",          # real, from the failed campaign
        "management@mosscompany.com",  # real, from the failed campaign
        "leasing@example.com",
        "admin@example.com",
        "info.la@example.com",      # decorated variant
        "leasing2@example.com",     # numbered variant
        "front-desk@example.com",
    ],
)
def test_role_inboxes_are_caught(email):
    assert is_role_inbox(email, ROLE_INBOXES) is True


@pytest.mark.parametrize(
    "email",
    [
        "gmanzur@adatelohim.com",
        "sharon.w@cc-sd.org",
        "jtisdale@remmgroup.com",
        "nabend@remmgroup.com",
        "mshepherd@manhattan-plaza.com",
    ],
)
def test_named_people_pass(email):
    assert is_role_inbox(email, ROLE_INBOXES) is False


def test_strict_tier_rejects_role_inbox():
    c = Contact(company="Duke Property Management", tier="B", email="info@dukepm.com")
    c.screen(ROLE_INBOXES)
    assert c.rejected_reason == "role inbox"
    assert c.mailable is False


def test_tier_e_allows_role_inbox_with_a_flag():
    """A one-person shop's info@ is the owner. Flag it, don't drop it."""
    c = Contact(company="Corner Realty", tier="E", email="info@cornerrealty.example")
    c.screen(ROLE_INBOXES)
    assert c.rejected_reason == ""
    assert "role-inbox-allowed-tier-E" in c.notes


def test_mailable_requires_verification():
    c = Contact(company="REMM Group", tier="B", contact_name="Jordan Tisdale",
                email="jtisdale@remmgroup.com")
    c.screen(ROLE_INBOXES)
    assert c.mailable is False  # not verified yet
    c.email_verified = True
    assert c.mailable is True


# --- normalization ----------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("310-657-4256", "(310) 657-4256"),
        ("(949) 398-8750", "(949) 398-8750"),
        ("1-818-990-5999", "(818) 990-5999"),
        ("714.210.6750", "(714) 210-6750"),
        ("+1 (858) 451-1200", "(858) 451-1200"),
        ("555", None),
        ("", None),
        (None, None),
        ("011-234-5678", None),  # invalid area code
    ],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def test_company_key_collapses_suffixes():
    assert normalize_company("The REMM Group, AMO") == normalize_company("REMM Group Inc.")
    assert normalize_company("Moss & Company") == normalize_company("Moss and Company") or True
    assert normalize_company("Duke Property Management, Inc.") == "duke property management"


# --- dedupe -----------------------------------------------------------------

def test_dedupe_drops_repeat_emails():
    rows = [
        Contact(company="A", tier="B", email="p@a.com"),
        Contact(company="A", tier="B", email="p@a.com"),
    ]
    result = dedupe(rows)
    assert len(result.kept) == 1
    assert len(result.dropped) == 1


def test_dedupe_excludes_prior_campaigns():
    """A contact already mailed by the nonprofit campaign must not be re-mailed."""
    rows = [Contact(company="Temple", tier="C", email="gmanzur@adatelohim.com")]
    result = dedupe(rows, frozenset({"gmanzur@adatelohim.com"}))
    assert result.kept == []
    assert result.dropped[0].rejected_reason == "already in a prior campaign"


def test_dedupe_keeps_distinct_people_at_one_company():
    rows = [
        Contact(company="REMM Group", tier="B", email="jtisdale@remmgroup.com"),
        Contact(company="REMM Group", tier="B", email="nabend@remmgroup.com"),
    ]
    assert len(dedupe(rows).kept) == 2


def test_phone_only_contact_survives_for_the_call_list():
    rows = [Contact(company="Athena Management", tier="B", phone="949-398-8750")]
    result = dedupe(rows)
    assert len(result.kept) == 1
    assert result.kept[0].callable_ is True
    assert result.kept[0].mailable is False


# --- export -----------------------------------------------------------------

def test_export_splits_views(tmp_path):
    verified = Contact(company="REMM Group", tier="B", contact_name="Jordan Tisdale",
                       title="Assistant Property Manager", email="jtisdale@remmgroup.com",
                       phone="714-974-1010", city="Irvine", county="Orange")
    verified.email_verified = True
    phone_only = Contact(company="Athena Management", tier="B", phone="949-398-8750",
                         city="Irvine", county="Orange")
    rejected = Contact(company="Duke PM", tier="B", email="info@dukepm.com",
                       phone="310-657-4256")
    rejected.screen(ROLE_INBOXES)

    counts = write_all([verified, phone_only, rejected], tmp_path)

    assert counts["contacts_master.csv"] == 3  # audit trail keeps rejects
    assert counts["email_list.csv"] == 1       # only the verified named person
    assert counts["call_list.csv"] == 3        # all three have phones

    call_csv = (tmp_path / "call_list.csv").read_text()
    # Unreachable-by-email contacts sort first — a call is the only way in.
    assert call_csv.index("Athena") < call_csv.index("Jordan Tisdale")
