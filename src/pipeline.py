"""End-to-end glue: file -> extract -> analyze -> anonymize -> output bytes.

Keeps the Streamlit app (and the recall harness) thin and testable. The heavy
detection lives in analyze.py; this module just orchestrates and produces the
downloadable anonymized file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .analyze import DEFAULT_SCORE_THRESHOLD, Entity, analyze_document
from .anonymize import Anonymization, anonymize
from .anonymize_files import anonymize_file
from .extract import ExtractedDoc, extract
from .redact_pdf import redact_values


@dataclass
class Processed:
    doc: ExtractedDoc
    entities: list[Entity] = field(default_factory=list)
    anonymization: Anonymization = field(default_factory=Anonymization)


def process_file(
    path: str | Path,
    engine,
    policy=None,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
) -> Processed:
    """Extract, analyze per-line, and anonymize a file end to end."""
    doc = extract(path)
    entities = analyze_document(doc, engine, score_threshold=score_threshold)
    anon = anonymize(doc.text, entities, policy=policy)
    return Processed(doc=doc, entities=entities, anonymization=anon)


def redaction_pairs(anon: Anonymization) -> list[tuple[str, str]]:
    """Unique (original_value -> token) pairs for locating values in a PDF."""
    seen: dict[str, str] = {}
    for rep in anon.replacements:
        seen.setdefault(rep.entity.text, rep.placeholder)
    return list(seen.items())


def write_anonymized_output(
    in_path: str | Path,
    out_path: str | Path,
    processed: Processed,
) -> None:
    """Produce the anonymized artifact matching the input type."""
    ext = Path(in_path).suffix.lower()
    if ext == ".pdf":
        redact_values(in_path, out_path, redaction_pairs(processed.anonymization))
    elif ext in (".docx", ".xlsx"):
        anonymize_file(in_path, out_path, processed.doc, processed.anonymization)
    else:
        raise ValueError(f"Unsupported output type: {ext!r}")
