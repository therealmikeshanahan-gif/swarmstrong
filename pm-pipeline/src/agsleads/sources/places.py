"""Build the company universe (and the phone column) from Google Places.

Places gives company name, address, phone and website. It does NOT give email
addresses — those come from the enrichment step. So this source alone is enough
to produce the call list, and is the input to the email list.

Needs GOOGLE_PLACES_API_KEY. Cost is per request; the full grid below is
roughly (cities x queries) requests, each returning up to 20 results with up to
3 pages. Budget accordingly before running statewide.
"""

from __future__ import annotations

import os
import time
from typing import Iterator

import requests

from ..contacts import Contact

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASK = ",".join([
    "places.displayName",
    "places.formattedAddress",
    "places.nationalPhoneNumber",
    "places.websiteUri",
    "places.primaryType",
    "nextPageToken",
])

# One query set per tier. Deliberately overlapping — dedupe cleans it up, and a
# firm that shows for two queries is usually a bigger firm.
TIER_QUERIES = {
    "B": [
        "commercial property management",
        "commercial real estate management",
        "office building management company",
        "retail property management",
    ],
    "C": [
        "HOA management company",
        "homeowners association management",
        "community association management",
    ],
    "D": [
        "apartment property management",
        "multifamily property management",
        "residential property management company",
    ],
    "F": [
        "shopping center management",
        "industrial park management",
        "self storage management company",
    ],
}


class PlacesError(RuntimeError):
    pass


def _post(payload: dict, api_key: str) -> dict:
    resp = requests.post(
        ENDPOINT,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise PlacesError(f"{resp.status_code}: {resp.text[:300]}")
    return resp.json()


def search(
    query: str,
    city: str,
    tier: str,
    county: str = "",
    api_key: str | None = None,
    max_pages: int = 3,
    pause: float = 0.3,
) -> Iterator[Contact]:
    """Yield Contacts for one query/city pair, following pagination."""
    api_key = api_key or os.environ.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise PlacesError("GOOGLE_PLACES_API_KEY is not set")

    payload = {"textQuery": f"{query} in {city}, CA", "languageCode": "en"}
    for page in range(max_pages):
        data = _post(payload, api_key)
        for place in data.get("places", []):
            yield Contact(
                company=(place.get("displayName") or {}).get("text", ""),
                tier=tier,
                city=city,
                county=county,
                phone=place.get("nationalPhoneNumber", "") or "",
                website=place.get("websiteUri", "") or "",
                source=f"places:{query}",
                notes=place.get("formattedAddress", "") or "",
            )
        token = data.get("nextPageToken")
        if not token:
            return
        payload = {"pageToken": token}
        time.sleep(pause)


def crawl(regions: dict, tiers: list[str] | None = None, **kwargs) -> Iterator[Contact]:
    """Walk every city in every region for every query in the selected tiers."""
    tiers = tiers or list(TIER_QUERIES)
    for region_name, region in regions.items():
        counties = ", ".join(region.get("counties", []))
        for city in region.get("cities", []):
            for tier in tiers:
                for query in TIER_QUERIES.get(tier, []):
                    try:
                        yield from search(query, city, tier, counties, **kwargs)
                    except PlacesError as exc:
                        print(f"  ! {region_name}/{city}/{tier}/{query}: {exc}")
