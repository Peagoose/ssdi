"""Tests for src/anonymize.py — typed placeholders, dedup, reading order, key."""
from __future__ import annotations

import csv

from src.analyze import Entity
from src.anonymize import anonymize, write_key_csv


def _ents(text, spans):
    """spans: list of (entity_type, substring) -> Entity at first occurrence."""
    out = []
    for etype, sub in spans:
        start = text.index(sub)
        out.append(Entity(etype, start, start + len(sub), 1.0, sub))
    return out


def test_typed_placeholders():
    text = "Sarah Chen, SSN 536-90-4788, email s@ex.com"
    ents = _ents(text, [("PERSON", "Sarah Chen"), ("US_SSN", "536-90-4788"),
                        ("EMAIL_ADDRESS", "s@ex.com")])
    result = anonymize(text, ents)
    assert "[NAME_1]" in result.text
    assert "[SSN_1]" in result.text
    assert "[EMAIL_1]" in result.text
    assert "Sarah Chen" not in result.text
    assert "536-90-4788" not in result.text


def test_same_value_same_placeholder():
    text = "Robert Alvarez signed. Robert Alvarez agreed. Maria Gomez left."
    ents = [
        Entity("PERSON", 0, 14, 1.0, "Robert Alvarez"),
        Entity("PERSON", 23, 37, 1.0, "Robert Alvarez"),
        Entity("PERSON", 46, 57, 1.0, "Maria Gomez"),
    ]
    result = anonymize(text, ents)
    # Two occurrences of the same name -> one placeholder, used twice
    assert result.text.count("[NAME_1]") == 2
    assert "[NAME_2]" in result.text
    row1 = next(r for r in result.key if r.placeholder == "[NAME_1]")
    assert row1.original == "Robert Alvarez" and row1.occurrences == 2


def test_reading_order_numbering():
    text = "Alice met Bob then Carol."
    ents = _ents(text, [("PERSON", "Alice"), ("PERSON", "Bob"), ("PERSON", "Carol")])
    result = anonymize(text, ents)
    order = [(r.placeholder, r.original) for r in result.key]
    assert order == [("[NAME_1]", "Alice"), ("[NAME_2]", "Bob"), ("[NAME_3]", "Carol")]


def test_numbers_per_type_independent():
    text = "536-90-4788 and 457-55-1462 for Alice"
    ents = _ents(text, [("US_SSN", "536-90-4788"), ("US_SSN", "457-55-1462"),
                        ("PERSON", "Alice")])
    result = anonymize(text, ents)
    assert "[SSN_1]" in result.text and "[SSN_2]" in result.text
    assert "[NAME_1]" in result.text  # name numbering independent of SSN numbering


def test_counts_by_type():
    text = "Alice Bob 536-90-4788"
    ents = _ents(text, [("PERSON", "Alice"), ("PERSON", "Bob"), ("US_SSN", "536-90-4788")])
    result = anonymize(text, ents)
    counts = result.counts_by_type()
    assert counts["PERSON"] == 2 and counts["US_SSN"] == 1


def test_key_csv_roundtrips(tmp_path):
    text = "Sarah Chen SSN 536-90-4788"
    ents = _ents(text, [("PERSON", "Sarah Chen"), ("US_SSN", "536-90-4788")])
    result = anonymize(text, ents)
    p = tmp_path / "key.csv"
    write_key_csv(p, result)
    rows = list(csv.DictReader(p.open()))
    # The key lets us reverse every placeholder back to its original value
    reverse = {r["placeholder"]: r["original_value"] for r in rows}
    assert reverse["[NAME_1]"] == "Sarah Chen"
    assert reverse["[SSN_1]"] == "536-90-4788"


def test_offsets_stay_valid_multiple_replacements():
    # Ensure right-to-left replacement keeps later text intact.
    text = "A=Alice B=Bob C=Carol"
    ents = _ents(text, [("PERSON", "Alice"), ("PERSON", "Bob"), ("PERSON", "Carol")])
    result = anonymize(text, ents)
    assert result.text == "A=[NAME_1] B=[NAME_2] C=[NAME_3]"
