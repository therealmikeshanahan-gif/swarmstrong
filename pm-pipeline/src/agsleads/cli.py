"""Run the pipeline.

    # 1. Universe + phones (needs GOOGLE_PLACES_API_KEY)
    python -m agsleads.cli build --tiers B,C --region orange_county

    # 2. Named contacts + verified emails (needs APOLLO_API_KEY, MILLIONVERIFIER_API_KEY)
    python -m agsleads.cli enrich --in out/contacts_master.csv

    # 3. Check one message against the reply guard
    python -m agsleads.cli check-reply < message.eml
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import yaml

from .contacts import Contact, dedupe, load_role_inboxes
from .export import write_all
from .identity import Identities
from .reply_guard import classify_raw

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
OUT = ROOT / "out"


def _load_regions(region: str | None) -> dict:
    regions = (yaml.safe_load((CONFIG / "counties.yml").read_text()) or {}).get("regions", {})
    if region:
        if region not in regions:
            sys.exit(f"unknown region '{region}'. known: {', '.join(regions)}")
        return {region: regions[region]}
    return regions


def _prior_contacts(path: str | None) -> frozenset[str]:
    """Addresses already loaded into any Instantly campaign — never mail twice."""
    if not path:
        return frozenset()
    rows = csv.DictReader(Path(path).open(encoding="utf-8"))
    return frozenset(
        (r.get("email") or "").strip().lower()
        for r in rows
        if (r.get("email") or "").strip()
    )


def cmd_build(args: argparse.Namespace) -> None:
    from .sources import places

    regions = _load_regions(args.region)
    tiers = [t.strip().upper() for t in args.tiers.split(",") if t.strip()]
    role_inboxes = load_role_inboxes(CONFIG / "role_inboxes.txt")

    print(f"crawling {len(regions)} region(s), tiers {tiers}")
    found = list(places.crawl(regions, tiers=tiers))
    print(f"  raw results: {len(found)}")

    screened = [c.screen(role_inboxes) for c in found]
    result = dedupe(screened, _prior_contacts(args.exclude))
    print(f"  {result.summary}")

    counts = write_all(result.kept + result.dropped, args.out)
    for name, n in counts.items():
        print(f"  {name}: {n} rows")
    print(f"\nCall list is ready now. Email list needs: cli.py enrich")


def cmd_enrich(args: argparse.Namespace) -> None:
    from .enrich import enrich_company, verify_all

    rows = list(csv.DictReader(Path(args.infile).open(encoding="utf-8")))
    companies = [
        Contact(**{k: v for k, v in r.items() if k in Contact.__dataclass_fields__
                   and k != "email_verified"})
        for r in rows
        if not r.get("contact_name")
    ]
    print(f"enriching {len(companies)} companies")

    people: list[Contact] = []
    for i, company in enumerate(companies, 1):
        people.extend(enrich_company(company))
        if i % 25 == 0:
            print(f"  {i}/{len(companies)}")

    role_inboxes = load_role_inboxes(CONFIG / "role_inboxes.txt")
    screened = [c.screen(role_inboxes) for c in people]
    print(f"  found {len(screened)} people; verifying")
    verified = verify_all(screened)

    result = dedupe(verified, _prior_contacts(args.exclude))
    print(f"  {result.summary}")
    counts = write_all(result.kept + result.dropped, args.out)
    for name, n in counts.items():
        print(f"  {name}: {n} rows")


def cmd_check_reply(args: argparse.Namespace) -> None:
    identities = Identities.load(CONFIG)
    raw = sys.stdin.buffer.read()
    v = classify_raw(raw, identities)
    print(f"kind     : {v.kind}")
    print(f"alert    : {v.alert}")
    print(f"responder: {v.responder}")
    print(f"opt-out  : {v.opt_out}")
    print(f"reason   : {v.reason}")
    sys.exit(0 if not v.alert else 10)  # 10 = a human needs to answer


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="agsleads")
    sub = parser.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="company universe + phone numbers")
    b.add_argument("--tiers", default="B,C,D")
    b.add_argument("--region", default=None, help="one region, or all if omitted")
    b.add_argument("--exclude", default=None, help="CSV of already-contacted emails")
    b.add_argument("--out", default=str(OUT))
    b.set_defaults(func=cmd_build)

    e = sub.add_parser("enrich", help="named contacts + verified emails")
    e.add_argument("--in", dest="infile", required=True)
    e.add_argument("--exclude", default=None)
    e.add_argument("--out", default=str(OUT))
    e.set_defaults(func=cmd_enrich)

    c = sub.add_parser("check-reply", help="classify one RFC822 message on stdin")
    c.set_defaults(func=cmd_check_reply)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
