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
        "info@example-propmgmt.com",          # real, from the failed campaign
        "management@example-realty2.com",  # real, from the failed campaign
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
        "dmorales@example-temple.org",
        "sgrant@example-cc.org",
        "jtisdale@example-regional.com",
        "nabend@example-regional.com",
        "mshepherd@example-plaza.com",
    ],
)
def test_named_people_pass(email):
    assert is_role_inbox(email, ROLE_INBOXES) is False


def test_strict_tier_rejects_role_inbox():
    c = Contact(company="Example Property Management", tier="B", email="info@example-propmgmt.com")
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
    c = Contact(company="Example Group", tier="B", contact_name="J. Tisdale",
                email="jtisdale@example-regional.com")
    c.screen(ROLE_INBOXES)
    assert c.mailable is False  # not verified yet
    c.email_verified = True
    assert c.mailable is True


# --- normalization ----------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("310-555-0101", "(310) 555-0101"),
        ("(949) 555-0102", "(949) 555-0102"),
        ("1-818-555-0103", "(818) 555-0103"),
        ("714.555.0104", "(714) 555-0104"),
        ("+1 (858) 555-0105", "(858) 555-0105"),
        ("555", None),
        ("", None),
        (None, None),
        ("011-234-5678", None),  # invalid area code
    ],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def test_company_key_collapses_suffixes():
    # Same firm written two ways must produce one key, or it gets mailed twice.
    assert normalize_company("The Example Group, AMO") == normalize_company("Example Group Inc.")
    assert normalize_company("Example Property Management, Inc.") == "example property management"
    assert normalize_company("  EXAMPLE   Realty, LLC ") == "example realty"
    assert normalize_company("Example Realty Co") == "example realty"


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
    rows = [Contact(company="Temple", tier="C", email="dmorales@example-temple.org")]
    result = dedupe(rows, frozenset({"dmorales@example-temple.org"}))
    assert result.kept == []
    assert result.dropped[0].rejected_reason == "already in a prior campaign"


def test_dedupe_keeps_distinct_people_at_one_company():
    rows = [
        Contact(company="Example Group", tier="B", email="jtisdale@example-regional.com"),
        Contact(company="Example Group", tier="B", email="nabend@example-regional.com"),
    ]
    assert len(dedupe(rows).kept) == 2


def test_phone_only_contact_survives_for_the_call_list():
    rows = [Contact(company="Example Management", tier="B", phone="949-555-0102")]
    result = dedupe(rows)
    assert len(result.kept) == 1
    assert result.kept[0].callable_ is True
    assert result.kept[0].mailable is False


# --- export -----------------------------------------------------------------

def test_export_splits_views(tmp_path):
    verified = Contact(company="Example Group", tier="B", contact_name="J. Tisdale",
                       title="Assistant Property Manager", email="jtisdale@example-regional.com",
                       phone="714-555-0106", city="Irvine", county="Orange")
    verified.email_verified = True
    phone_only = Contact(company="Example Management", tier="B", phone="949-555-0102",
                         city="Irvine", county="Orange")
    rejected = Contact(company="Example PM", tier="B", email="info@example-propmgmt.com",
                       phone="310-555-0101")
    rejected.screen(ROLE_INBOXES)

    counts = write_all([verified, phone_only, rejected], tmp_path)

    assert counts["contacts_master.csv"] == 3  # audit trail keeps rejects
    assert counts["email_list.csv"] == 1       # only the verified named person
    assert counts["call_list.csv"] == 3        # all three have phones

    call_csv = (tmp_path / "call_list.csv").read_text()
    # Unreachable-by-email contacts sort first — a call is the only way in.
    assert call_csv.index("Example Management") < call_csv.index("J. Tisdale")
