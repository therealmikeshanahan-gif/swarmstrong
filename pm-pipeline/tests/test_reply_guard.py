"""Regression tests for the Oct 12 false-alert bug.

Every fixture here is a real message from the campaigns, not a hypothetical.
The two `outbound_*` fixtures are the exact messages that produced bogus
"NEW LEAD REPLY" alerts for Example Property Management and Example Realty Co.
"""

from pathlib import Path

import pytest

from agsleads.identity import Identities
from agsleads.reply_guard import classify_raw

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
IDENTITIES = Identities.load(ROOT / "config")


def verdict_for(name: str):
    return classify_raw((FIXTURES / name).read_bytes(), IDENTITIES)


# --- the actual bug ---------------------------------------------------------

@pytest.mark.parametrize(
    "fixture",
    ["outbound_step4_a.eml", "outbound_step4_b.eml"],
)
def test_our_own_step4_is_never_a_lead(fixture):
    """These two fired false alerts on Oct 12. They must never alert again."""
    v = verdict_for(fixture)
    assert v.kind == "outbound_self"
    assert v.alert is False
    assert v.is_real_reply is False


def test_our_own_optout_line_is_not_read_as_an_optout():
    """Our copy ends with 'Reply "no thanks" to opt out.'

    If direction were checked after opt-out detection we would mark our own
    prospects as opted out and silently burn the list.
    """
    v = verdict_for("outbound_step4_a.eml")
    assert v.kind == "outbound_self"
    assert v.opt_out is False


def test_forwarded_alert_does_not_loop():
    """The watcher's own alert mail must not be re-ingested as a new lead."""
    v = verdict_for("forwarded_alert_internal.eml")
    assert v.kind == "outbound_self"
    assert v.alert is False


# --- real replies must still get through ------------------------------------

def test_real_human_reply_alerts():
    v = verdict_for("reply_named_person.eml")
    assert v.kind == "human_reply"
    assert v.alert is True
    assert v.responder == "dmorales@example-temple.org"


def test_role_inbox_reply_still_counts_as_human():
    """info@example-church.org sent a real, high-intent human reply.

    Role inboxes are bad targets when BUILDING a list, but a reply from one is
    still a human. Never suppress on the shape of the address.
    """
    v = verdict_for("reply_from_role_inbox.eml")
    assert v.kind == "human_reply"
    assert v.alert is True


def test_optout_reply_is_flagged_and_still_surfaces():
    v = verdict_for("reply_optout.eml")
    assert v.kind == "human_reply"
    assert v.opt_out is True


# --- noise must stay quiet --------------------------------------------------

def test_autoreply_does_not_page_anyone():
    v = verdict_for("autoreply_ooo.eml")
    assert v.kind == "autoreply"
    assert v.alert is False


def test_bounce_is_not_a_reply():
    v = verdict_for("bounce_dsn.eml")
    assert v.kind == "bounce"
    assert v.alert is False


# --- identity matching ------------------------------------------------------

@pytest.mark.parametrize(
    "address",
    [
        "sender1@example-outreach.com",
        "sender2@example-outreach.com",
        "sender3@example-outreach.com",
        "persona@example-grants.com",
        "anything@example-main.com",  # domain-level match
        "SENDER1@Example-Outreach.com",  # case-insensitive
    ],
)
def test_owned_addresses(address):
    assert IDENTITIES.owns_address(address) is True


@pytest.mark.parametrize(
    "address",
    [
        "dmorales@example-temple.org",
        "info@example-propmgmt.com",
        "sgrant@example-cc.org",
        "notexample-outreach.com@evil.example",
    ],
)
def test_outside_addresses(address):
    assert IDENTITIES.owns_address(address) is False


def test_true_reply_count_for_oc_la_property_managers():
    """The campaign dashboard said 3 replies. The real number was 0.

    Feed it every message we have from that campaign and confirm the guard
    reports zero real replies.
    """
    campaign_messages = ["outbound_step4_a.eml", "outbound_step4_b.eml"]
    real = [v for v in map(verdict_for, campaign_messages) if v.is_real_reply]
    assert len(real) == 0
