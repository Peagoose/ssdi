"""Anonymization: resolved entities -> typed, reversible placeholders + CSV key.

Rules baked in:
  * Typed placeholders: PERSON -> [NAME_1], US_SSN -> [SSN_1], etc.
  * Same surface value -> same placeholder within a document (so a name repeated
    across a table and the body collapses to one placeholder).
  * Placeholders are numbered in READING ORDER (first occurrence by offset), so the
    key is stable and easy to audit.
  * A separate CSV re-identification key maps each placeholder back to its original
    value and occurrence count.

This module does raw placeholder substitution. The FRCP-style partial redaction
policy (SSN -> last 4, DOB -> year, minors -> initials) is applied on top in
policy.py (Task 6), which rewrites entity values before anonymization.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from .analyze import Entity

# entity_type -> placeholder prefix. Anything unmapped falls back to the raw
# entity type name, so a new recognizer still produces a sane placeholder.
PLACEHOLDER_PREFIXES: dict[str, str] = {
    "PERSON": "NAME",
    "US_SSN": "SSN",
    "US_ITIN": "ITIN",
    "US_EIN": "EIN",
    "US_BANK_ROUTING": "ROUTING",
    "US_BANK_NUMBER": "ACCOUNT",
    "CREDIT_CARD": "CARD",
    "IBAN_CODE": "IBAN",
    "US_COURT_DOCKET": "DOCKET",
    "US_BAR_NUMBER": "BAR",
    "US_DRIVER_LICENSE": "DL",
    "US_PASSPORT": "PASSPORT",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "LOCATION": "LOCATION",
    "GPE": "LOCATION",
    "ORG": "ORG",
    "ORGANIZATION": "ORG",
    "NRP": "NRP",
    "DATE_TIME": "DATE",
    "IP_ADDRESS": "IP",
    "URL": "URL",
    "CRYPTO": "CRYPTO",
}


def prefix_for(entity_type: str, overrides: dict[str, str] | None = None) -> str:
    if overrides and entity_type in overrides:
        return overrides[entity_type]
    return PLACEHOLDER_PREFIXES.get(entity_type, entity_type)


@dataclass
class Replacement:
    """One detected entity and the placeholder it was assigned."""
    entity: Entity
    placeholder: str


@dataclass
class KeyRow:
    placeholder: str
    entity_type: str
    original: str
    occurrences: int = 0


@dataclass
class Anonymization:
    text: str = ""
    replacements: list[Replacement] = field(default_factory=list)
    key: list[KeyRow] = field(default_factory=list)

    def counts_by_type(self) -> dict[str, int]:
        """Per-entity-type count of placeholders (distinct values)."""
        counts: dict[str, int] = {}
        for row in self.key:
            counts[row.entity_type] = counts.get(row.entity_type, 0) + 1
        return counts


def anonymize(
    text: str,
    entities: list[Entity],
    prefix_overrides: dict[str, str] | None = None,
    policy=None,
) -> Anonymization:
    """Replace entity spans in `text` with typed, deduplicated placeholders.

    `entities` must carry offsets into `text` (as produced by analyze_document).
    Overlapping entities should already be resolved upstream; if any remain, the
    earlier-starting one is applied and later overlaps are skipped.

    If `policy` (a RedactionPolicy) is given, governed types render a legal-style
    partial mask (e.g. SSN -> "XXX-XX-4788") instead of a generic placeholder.
    Every distinct original still gets its own key row, so redaction stays
    reversible via the CSV key.
    """
    ordered = sorted(entities, key=lambda e: (e.start, e.end))

    mapping: dict[tuple[str, str], str] = {}       # (type, value) -> token
    counters: dict[str, int] = {}                  # prefix -> next number
    key_rows: dict[tuple[str, str], KeyRow] = {}   # (type, value) -> KeyRow
    replacements: list[Replacement] = []

    for entity in ordered:
        value = entity.text
        map_key = (entity.entity_type, value)
        if map_key not in mapping:
            token = policy.render(entity.entity_type, value) if policy else None
            if token is None:
                prefix = prefix_for(entity.entity_type, prefix_overrides)
                counters[prefix] = counters.get(prefix, 0) + 1
                token = f"[{prefix}_{counters[prefix]}]"
            mapping[map_key] = token
            key_rows[map_key] = KeyRow(
                placeholder=token,
                entity_type=entity.entity_type,
                original=value,
            )
        token = mapping[map_key]
        key_rows[map_key].occurrences += 1
        replacements.append(Replacement(entity=entity, placeholder=token))

    # Apply replacements right-to-left so earlier offsets stay valid. Skip any
    # leftover overlap defensively.
    out = text
    last_start = len(text) + 1
    for rep in sorted(replacements, key=lambda r: r.entity.start, reverse=True):
        e = rep.entity
        if e.end > last_start:  # overlaps a span we already replaced
            continue
        out = out[: e.start] + rep.placeholder + out[e.end :]
        last_start = e.start

    # Key rows in first-occurrence (reading) order.
    key = list(key_rows.values())
    return Anonymization(text=out, replacements=replacements, key=key)


def write_key_csv(path: str | Path, anonymization: Anonymization) -> None:
    """Write the re-identification key to CSV: placeholder, type, original, count."""
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["placeholder", "entity_type", "original_value", "occurrences"])
        for row in anonymization.key:
            writer.writerow(
                [row.placeholder, row.entity_type, row.original, row.occurrences]
            )
