"""Who we are, for the purpose of telling our own mail apart from a prospect's."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from email.utils import getaddresses
from pathlib import Path

import yaml

_ADDR_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def extract_addresses(header_value: str | None) -> list[str]:
    """Pull bare addresses out of a header, however badly it is formatted.

    Falls back to a regex scan because forwarded alert bodies often carry
    half-formed headers that getaddresses() returns empty for.
    """
    if not header_value:
        return []
    found = [addr.lower() for _name, addr in getaddresses([header_value]) if addr]
    if not found:
        found = [m.group(0).lower() for m in _ADDR_RE.finditer(header_value)]
    return found


@dataclass(frozen=True)
class Identities:
    domains: frozenset[str] = field(default_factory=frozenset)
    addresses: frozenset[str] = field(default_factory=frozenset)
    content_markers: tuple[str, ...] = ()

    @staticmethod
    def resolve(config_dir: str | Path) -> Path:
        """Pick the real identity file, falling back to the committed example.

        `identities.yml` holds live mailboxes and is deliberately NOT in version
        control — this repo is public. `identities.example.yml` ships with
        placeholder addresses so the tests run out of the box on a fresh clone.
        Copy the example to `identities.yml` and fill in the real values on any
        machine that actually runs the pipeline.
        """
        real = Path(config_dir) / "identities.yml"
        return real if real.exists() else Path(config_dir) / "identities.example.yml"

    @classmethod
    def load(cls, path: str | Path) -> "Identities":
        path = Path(path)
        if path.is_dir():
            path = cls.resolve(path)
        data = yaml.safe_load(path.read_text()) or {}
        return cls(
            domains=frozenset(d.lower().lstrip("@") for d in data.get("owned_domains", [])),
            addresses=frozenset(a.lower() for a in data.get("owned_addresses", [])),
            content_markers=tuple(data.get("own_content_markers", [])),
        )

    def owns_address(self, address: str | None) -> bool:
        if not address:
            return False
        address = address.strip().lower()
        if address in self.addresses:
            return True
        _, _, domain = address.partition("@")
        return bool(domain) and domain in self.domains

    def owns_any(self, header_value: str | None) -> bool:
        return any(self.owns_address(a) for a in extract_addresses(header_value))

    def body_looks_like_ours(self, body: str | None) -> bool:
        if not body or not self.content_markers:
            return False
        return any(marker.lower() in body.lower() for marker in self.content_markers)
