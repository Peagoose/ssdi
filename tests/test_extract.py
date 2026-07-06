"""Tests for src/extract.py — proves real extraction across PDF/DOCX/XLSX,
including table rows/cells, with line boundaries preserved.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.extract import extract, ExtractedDoc
from tests.make_min_fixtures import make_docx, make_pdf, make_xlsx


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("fixtures")
    make_docx(d / "min.docx")
    make_xlsx(d / "min.xlsx")
    make_pdf(d / "min.pdf")
    return d


def test_docx_extracts_paragraphs_and_table_cells(fixtures: Path):
    doc = extract(fixtures / "min.docx")
    assert isinstance(doc, ExtractedDoc)
    text = doc.text
    assert "Sarah Chen" in text
    # table cells become their own lines, not merged into one blob
    assert any(l.text == "Robert Alvarez" for l in doc.lines)
    assert any(l.text == "536-90-4788" for l in doc.lines)
    # a table cell line is tagged with a table source
    assert any(l.source.startswith("table") for l in doc.lines)


def test_xlsx_extracts_one_line_per_cell_with_source(fixtures: Path):
    doc = extract(fixtures / "min.xlsx")
    # each non-empty cell is its own line (per-line lesson for spreadsheets)
    ssn_lines = [l for l in doc.lines if l.text == "536-90-4788"]
    assert ssn_lines, "SSN cell should be extracted"
    assert ssn_lines[0].source.startswith("Parties!"), ssn_lines[0].source
    assert any(l.text == "(212) 555-0182" for l in doc.lines)


def test_pdf_extracts_lines(fixtures: Path):
    doc = extract(fixtures / "min.pdf")
    text = doc.text
    assert "Sarah Chen" in text
    assert "536-90-4788" in text
    # lines are preserved, not collapsed to a single line
    assert len(doc.lines) >= 3
    assert all(l.source.startswith("p") for l in doc.lines)


def test_text_property_matches_lines(fixtures: Path):
    doc = extract(fixtures / "min.docx")
    assert doc.text == "\n".join(l.text for l in doc.lines)


def test_unsupported_extension_raises(tmp_path: Path):
    bad = tmp_path / "note.txt"
    bad.write_text("hello")
    with pytest.raises(ValueError):
        extract(bad)


def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        extract(tmp_path / "nope.pdf")
