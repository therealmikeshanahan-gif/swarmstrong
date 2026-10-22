"""Guard against the two files that must agree drifting apart.

The Apps Script watcher carries its own copy of the owned-identity lists,
because Apps Script cannot read config/identities.yml. If someone adds a
sending domain to one and not the other, the false alerts come back on
whichever side was missed — so that mistake fails a test instead.
"""

import json
import re
from pathlib import Path

import yaml

from agsleads.identity import Identities

ROOT = Path(__file__).resolve().parents[1]
GS = (ROOT / "apps-script" / "replyGuard.gs").read_text()
CONF = yaml.safe_load(Identities.resolve(ROOT / "config").read_text())


def js_array(name: str) -> list[str]:
    """Pull a `var NAME = [...]` literal out of the .gs file."""
    match = re.search(rf"var\s+{name}\s*=\s*\[(.*?)\];", GS, re.S)
    assert match, f"{name} not found in replyGuard.gs"
    return re.findall(r"'([^']*)'", match.group(1))


def test_owned_domains_match():
    assert sorted(js_array("OWNED_DOMAINS")) == sorted(CONF["owned_domains"])


def test_owned_addresses_match():
    assert sorted(js_array("OWNED_ADDRESSES")) == sorted(CONF["owned_addresses"])


def test_content_markers_match():
    """Markers use double quotes inside, so compare after normalising quotes."""
    match = re.search(r"var\s+OWN_CONTENT_MARKERS\s*=\s*\[(.*?)\];", GS, re.S)
    assert match
    js_markers = re.findall(r"'([^']*)'", match.group(1))
    assert sorted(js_markers) == sorted(CONF["own_content_markers"])


def test_golden_matches_current_python():
    """expected_verdicts.json is what the JS is held to. Keep it honest."""
    from agsleads.identity import Identities
    from agsleads.reply_guard import classify_raw

    golden = json.loads((ROOT / "tests" / "fixtures" / "expected_verdicts.json").read_text())
    identities = Identities.load(ROOT / "config")

    for name, expected in golden.items():
        verdict = classify_raw((ROOT / "tests" / "fixtures" / name).read_bytes(), identities)
        assert verdict.kind == expected["kind"], f"{name}: golden is stale"
        assert verdict.alert == expected["alert"], f"{name}: golden is stale"
        assert verdict.opt_out == expected["optOut"], f"{name}: golden is stale"
        assert verdict.responder == expected["responder"], f"{name}: golden is stale"
