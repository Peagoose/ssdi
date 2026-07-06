"""Tests for the measurement harness (pure scoring) + labeled-set generation."""
from __future__ import annotations

from pathlib import Path

from src.measure import evaluate
from src.testset import generate_labeled_set


def test_value_recall_counts_detected_values():
    expected = [("US_SSN", "536-90-4788"), ("US_SSN", "457-55-1462"),
                ("PERSON", "Sarah Chen")]
    detected = [("US_SSN", "536-90-4788"), ("PERSON", "Sarah Chen")]
    r = evaluate(expected, detected)
    assert r.per_type["US_SSN"].expected == 2
    assert r.per_type["US_SSN"].value_hits == 1
    assert r.per_type["US_SSN"].value_recall == 0.5
    assert r.per_type["PERSON"].value_recall == 1.0
    assert round(r.overall_value_recall, 2) == round(2 / 3, 2)


def test_numeric_match_is_format_insensitive():
    # detected without dashes still matches expected with dashes (digits compared)
    r = evaluate([("US_SSN", "536-90-4788")], [("US_SSN", "536904788")])
    assert r.per_type["US_SSN"].value_hits == 1


def test_numeric_partial_does_not_match():
    # last-4 must NOT count as detecting the full SSN
    r = evaluate([("US_SSN", "536-90-4788")], [("US_SSN", "4788")])
    assert r.per_type["US_SSN"].value_hits == 0


def test_typed_vs_value_recall_distinguished():
    # value detected but under a different label -> value hit, not typed hit
    r = evaluate([("US_DOB", "03/14/1985")], [("DATE_TIME", "03/14/1985")])
    assert r.per_type["US_DOB"].value_hits == 1
    assert r.per_type["US_DOB"].typed_hits == 1  # DATE_TIME is equiv to US_DOB
    r2 = evaluate([("US_SSN", "536-90-4788")], [("US_BANK_ROUTING", "536904788")])
    assert r2.per_type["US_SSN"].value_hits == 1
    assert r2.per_type["US_SSN"].typed_hits == 0


def test_location_equivalence():
    r = evaluate([("LOCATION", "123 Main Street")], [("GPE", "123 Main Street")])
    assert r.per_type["LOCATION"].typed_hits == 1


def test_precision():
    expected = [("PERSON", "Sarah Chen")]
    detected = [("PERSON", "Sarah Chen"), ("ORG", "Random Corp")]  # 1 TP, 1 FP
    r = evaluate(expected, detected)
    assert r.precision == 0.5


def test_generate_labeled_set_creates_files_and_table_doc(tmp_path: Path):
    labeled = generate_labeled_set(tmp_path)
    names = {ld.path.name for ld in labeled}
    assert {"contract.docx", "pleading.pdf", "parties.xlsx"} <= names
    for ld in labeled:
        assert ld.path.exists() and ld.entities
    # The workbook is the table-heavy stress doc: many labeled rows
    parties = next(ld for ld in labeled if ld.path.name == "parties.xlsx")
    assert len([e for e in parties.entities if e[0] == "US_SSN"]) >= 4
