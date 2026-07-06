"""Tests for src/analyze.py.

These exercise MY orchestration logic (span trimming, overlap resolution,
per-line -> global offset mapping) with a stub engine, plus the real offline
email hardening. Real neural detection is covered by the smoke test on Windows;
here we don't need the model.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.analyze import (
    Entity,
    analyze_document,
    force_tldextract_offline,
    resolve_overlaps,
    trim_span,
)
from src.extract import ExtractedDoc, Line


# --------------------------------------------------------------------------- #
# Offline email hardening (real)
# --------------------------------------------------------------------------- #
def test_email_validation_offline():
    force_tldextract_offline()
    from presidio_analyzer.predefined_recognizers import EmailRecognizer

    rec = EmailRecognizer()
    # validate_result must succeed using the bundled snapshot, no network.
    assert rec.validate_result("sarah.chen@example.com") is True
    assert rec.validate_result("not-an-email") is False


# --------------------------------------------------------------------------- #
# Span trimming
# --------------------------------------------------------------------------- #
def test_trim_span_strips_edges_not_interior():
    text = "  (john.doe@example.com).  "
    s, e = trim_span(text, 0, len(text))
    assert text[s:e] == "john.doe@example.com"


def test_trim_span_keeps_ssn_dashes():
    text = "SSN: 536-90-4788,"
    start = text.index("536")
    s, e = trim_span(text, start, len(text))
    assert text[s:e] == "536-90-4788"


# --------------------------------------------------------------------------- #
# Overlap resolution: deterministic beats NER
# --------------------------------------------------------------------------- #
def test_deterministic_beats_ner_on_overlap():
    # An NER PERSON and a regex US_SSN claim the same span; SSN must win.
    ner = Entity("PERSON", 0, 11, 0.85, "536-90-4788")
    ssn = Entity("US_SSN", 0, 11, 0.60, "536-90-4788")
    chosen = resolve_overlaps([ner, ssn])
    assert len(chosen) == 1
    assert chosen[0].entity_type == "US_SSN"


def test_higher_score_wins_within_same_class():
    a = Entity("PERSON", 0, 5, 0.40, "Smith")
    b = Entity("PERSON", 0, 5, 0.90, "Smith")
    chosen = resolve_overlaps([a, b])
    assert len(chosen) == 1 and chosen[0].score == 0.90


def test_non_overlapping_all_kept():
    a = Entity("PERSON", 0, 5, 0.9, "Alice")
    b = Entity("US_SSN", 10, 21, 1.0, "536-90-4788")
    chosen = resolve_overlaps([a, b])
    assert len(chosen) == 2


# --------------------------------------------------------------------------- #
# Per-line analysis with global offset mapping (stub engine)
# --------------------------------------------------------------------------- #
@dataclass
class _R:
    entity_type: str
    start: int
    end: int
    score: float


class _StubEngine:
    """Returns canned results per line text; verifies offsets are line-local in
    and global out."""

    def __init__(self, table):
        self.table = table

    def analyze(self, text, language, entities, score_threshold):
        return self.table.get(text, [])


def test_analyze_document_maps_to_global_offsets():
    doc = ExtractedDoc(
        lines=[
            Line("Plaintiff Sarah Chen", "para0"),
            Line("SSN 536-90-4788", "table0:r1c1"),
        ],
        filetype="docx",
    )
    stub = _StubEngine(
        {
            "Plaintiff Sarah Chen": [_R("PERSON", 10, 20, 0.9)],   # "Sarah Chen"
            "SSN 536-90-4788": [_R("US_SSN", 4, 15, 1.0)],         # "536-90-4788"
        }
    )
    ents = analyze_document(doc, stub)
    by_type = {e.entity_type: e for e in ents}
    # Global offsets must slice the right substrings out of doc.text
    assert doc.text[by_type["PERSON"].start:by_type["PERSON"].end] == "Sarah Chen"
    assert doc.text[by_type["US_SSN"].start:by_type["US_SSN"].end] == "536-90-4788"
    # sources are carried through
    assert by_type["US_SSN"].source == "table0:r1c1"


def test_analyze_document_trims_and_resolves_per_line():
    doc = ExtractedDoc(lines=[Line("Name Robert Alvarez ", "para0")], filetype="docx")
    # NER returns a padded span with trailing space + an overlapping ORG; PERSON wins
    stub = _StubEngine(
        {
            "Name Robert Alvarez ": [
                _R("PERSON", 5, 20, 0.9),   # "Robert Alvarez " (trailing space)
                _R("PERSON", 5, 19, 0.4),
            ]
        }
    )
    ents = analyze_document(doc, stub)
    assert len(ents) == 1
    assert doc.text[ents[0].start:ents[0].end] == "Robert Alvarez"  # trimmed
