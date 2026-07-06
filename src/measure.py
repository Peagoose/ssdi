"""Recall / precision measurement on the labeled synthetic test set.

Answers the spike's core question: does detection work well enough on real legal
English, including tables? Reports per-entity-type recall (did we catch the value)
and precision, with a spotlight on the table-heavy workbook.

Run (Windows, venv active, model installed):
    python -m src.measure

Writes results/recall.csv and prints a per-type table. The scoring logic
(`evaluate`) is pure and unit-tested; only the full run needs the NER model.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from .analyze import DEFAULT_SCORE_THRESHOLD, analyze_document
from .extract import extract
from .testset import LabeledDoc, generate_labeled_set

# Types whose values are compared by exact concatenated digits.
_NUMERIC_TYPES = {
    "US_SSN", "US_ITIN", "US_EIN", "US_BANK_ROUTING", "US_BANK_NUMBER",
    "CREDIT_CARD", "IBAN_CODE", "PHONE_NUMBER", "US_BAR_NUMBER",
}
# Detected types that count as a match for a given expected type.
_EQUIV: dict[str, set[str]] = {
    "LOCATION": {"LOCATION", "GPE"},
    "ORG": {"ORG", "ORGANIZATION"},
    "US_DOB": {"US_DOB", "DATE_TIME"},
    "US_COURT_DOCKET": {"US_COURT_DOCKET"},
}

_WS = re.compile(r"\s+")
_NON_DIGIT = re.compile(r"\D")


def _equiv(entity_type: str) -> set[str]:
    return _EQUIV.get(entity_type, {entity_type})


def _norm(entity_type: str, value: str) -> str:
    if entity_type in _NUMERIC_TYPES:
        return _NON_DIGIT.sub("", value)
    return _WS.sub(" ", value.strip()).casefold()


def _text_match(a: str, b: str) -> bool:
    if a == b:
        return True
    # tolerate span differences for names/orgs/locations
    return len(a) >= 4 and len(b) >= 4 and (a in b or b in a)


def _matches(expected_type: str, expected_val: str, det_type: str, det_val: str,
             typed: bool) -> bool:
    if typed and det_type not in _equiv(expected_type):
        return False
    numeric = expected_type in _NUMERIC_TYPES
    en = _norm(expected_type, expected_val)
    dn = _norm(det_type if typed else expected_type, det_val)
    if numeric:
        return en == dn and en != ""
    return _text_match(en, dn)


# --------------------------------------------------------------------------- #
# Pure scoring
# --------------------------------------------------------------------------- #
@dataclass
class TypeScore:
    entity_type: str
    expected: int = 0
    value_hits: int = 0   # detected at all (redacted), ignoring the label
    typed_hits: int = 0   # detected AND labeled with a compatible type

    @property
    def value_recall(self) -> float:
        return self.value_hits / self.expected if self.expected else 0.0

    @property
    def typed_recall(self) -> float:
        return self.typed_hits / self.expected if self.expected else 0.0


@dataclass
class Report:
    per_type: dict[str, TypeScore] = field(default_factory=dict)
    total_expected: int = 0
    total_value_hits: int = 0
    detected_total: int = 0
    detected_true: int = 0  # detected entities whose value matches some expected

    @property
    def overall_value_recall(self) -> float:
        return self.total_value_hits / self.total_expected if self.total_expected else 0.0

    @property
    def precision(self) -> float:
        return self.detected_true / self.detected_total if self.detected_total else 0.0


def evaluate(
    expected: list[tuple[str, str]],
    detected: list[tuple[str, str]],
) -> Report:
    """Compare expected vs detected (type, value) pairs. Pure — no I/O, no model."""
    report = Report()
    for etype, eval_ in expected:
        score = report.per_type.setdefault(etype, TypeScore(entity_type=etype))
        score.expected += 1
        report.total_expected += 1

        value_hit = any(_matches(etype, eval_, dt, dv, typed=False) for dt, dv in detected)
        typed_hit = any(_matches(etype, eval_, dt, dv, typed=True) for dt, dv in detected)
        if value_hit:
            score.value_hits += 1
            report.total_value_hits += 1
        if typed_hit:
            score.typed_hits += 1

    # Precision: a detected entity is "true" if its value matches any expected value.
    report.detected_total = len(detected)
    for dt, dv in detected:
        if any(_matches(et, ev, dt, dv, typed=False) for et, ev in expected):
            report.detected_true += 1
    return report


# --------------------------------------------------------------------------- #
# Full run (needs the NER model)
# --------------------------------------------------------------------------- #
def _detected_for(doc_path: Path, engine, threshold: float) -> list[tuple[str, str]]:
    doc = extract(doc_path)
    ents = analyze_document(doc, engine, score_threshold=threshold)
    return [(e.entity_type, e.text) for e in ents]


def run(
    engine,
    out_dir: str | Path = "test_files/labeled",
    results_dir: str | Path = "results",
    threshold: float = DEFAULT_SCORE_THRESHOLD,
) -> Report:
    labeled: list[LabeledDoc] = generate_labeled_set(out_dir)
    expected: list[tuple[str, str]] = []
    detected: list[tuple[str, str]] = []
    for ld in labeled:
        expected += ld.entities
        detected += _detected_for(ld.path, engine, threshold)

    report = evaluate(expected, detected)
    _write_csv(report, Path(results_dir) / "recall.csv")
    _print(report)
    return report


def _write_csv(report: Report, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["entity_type", "expected", "value_hits", "value_recall",
                    "typed_hits", "typed_recall"])
        for s in sorted(report.per_type.values(), key=lambda x: x.entity_type):
            w.writerow([s.entity_type, s.expected, s.value_hits,
                        f"{s.value_recall:.2f}", s.typed_hits, f"{s.typed_recall:.2f}"])
        w.writerow([])
        w.writerow(["OVERALL value recall", f"{report.overall_value_recall:.2f}"])
        w.writerow(["OVERALL precision", f"{report.precision:.2f}"])


def _print(report: Report) -> None:
    print(f"\n{'ENTITY':<18}{'EXP':>4}{'VAL-REC':>9}{'TYP-REC':>9}")
    print("-" * 40)
    for s in sorted(report.per_type.values(), key=lambda x: x.entity_type):
        print(f"{s.entity_type:<18}{s.expected:>4}{s.value_recall:>9.2f}{s.typed_recall:>9.2f}")
    print("-" * 40)
    print(f"{'OVERALL':<18}{report.total_expected:>4}{report.overall_value_recall:>9.2f}")
    print(f"Precision (labeled): {report.precision:.2f}")
    print("Note: value-recall = did we detect/redact the value at all; "
          "typed-recall also requires the right label.")


def main() -> int:
    try:
        from .analyze import build_analyzer_engine
        engine = build_analyzer_engine()
    except OSError:
        print("Model 'en_core_web_lg' not found. Run: python -m spacy download en_core_web_lg")
        return 1
    run(engine)
    print("\nWrote results/recall.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
