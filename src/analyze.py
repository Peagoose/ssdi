"""Analysis pipeline: extracted document -> resolved PII entities.

Bakes in the hard-won lessons:
  * Run NER **per line**, not on the whole document (tables with numbers between
    rows wreck recall otherwise).
  * Deterministic regex/checksum detectors **win over NER** on any span overlap.
  * Trim whitespace/punctuation off span edges so a placeholder lands exactly on
    the value.
  * Fully offline: the email recognizer's TLD lookup is forced to a bundled
    snapshot so nothing touches the network.

Entity offsets returned by `analyze_document` are GLOBAL offsets into
`ExtractedDoc.text` (lines joined by "\n"), so anonymize.py and the UI can map
them straight onto the same text the user sees.
"""
from __future__ import annotations

from dataclasses import dataclass

from .extract import ExtractedDoc
from .recognizers import (
    DETERMINISTIC_ENTITIES,
    custom_recognizers,
)

DEFAULT_SCORE_THRESHOLD = 0.35
DEFAULT_MODEL = "en_core_web_lg"

# Characters trimmed from the EDGES of a detected span (never the interior, so
# email dots and SSN dashes are preserved).
_EDGE_CHARS = " \t\r\n.,;:!?\"'`()[]{}<>|"


@dataclass
class Entity:
    """A resolved PII entity, positioned in the document's canonical text."""
    entity_type: str
    start: int
    end: int
    score: float
    text: str
    source: str = ""


# --------------------------------------------------------------------------- #
# Offline hardening
# --------------------------------------------------------------------------- #
def force_tldextract_offline() -> None:
    """Make Presidio's email TLD validation offline.

    Presidio's EmailRecognizer calls ``tldextract.extract`` which, by default,
    tries to refresh the public-suffix list over the network. We replace the
    module-level function with an extractor that uses only the bundled snapshot,
    so the tool is genuinely offline and prints no network noise.
    """
    import tldextract

    offline = tldextract.TLDExtract(suffix_list_urls=())  # no fetch; snapshot only
    tldextract.extract = offline


# --------------------------------------------------------------------------- #
# Engine construction
# --------------------------------------------------------------------------- #
def build_analyzer_engine(model_name: str = DEFAULT_MODEL):
    """Build a Presidio AnalyzerEngine: spaCy NER + predefined + custom recognizers.

    Predefined recognizers already provide CREDIT_CARD (Luhn) and IBAN_CODE (mod-97),
    plus EMAIL/PHONE/US_SSN/US_BANK_NUMBER/US_DRIVER_LICENSE/US_PASSPORT/US_ITIN and
    the NER-backed PERSON/LOCATION/ORG mappings — we REUSE all of those. We only ADD
    the five custom recognizers (SSN structure/EIN/routing checksum/docket/bar).
    """
    force_tldextract_offline()

    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": model_name}],
    }
    nlp_engine = NlpEngineProvider(nlp_configuration=configuration).create_engine()

    registry = RecognizerRegistry()
    registry.load_predefined_recognizers(languages=["en"], nlp_engine=nlp_engine)
    for recognizer in custom_recognizers():
        registry.add_recognizer(recognizer)

    return AnalyzerEngine(
        nlp_engine=nlp_engine,
        registry=registry,
        supported_languages=["en"],
    )


# --------------------------------------------------------------------------- #
# Span trimming + overlap resolution (pure, unit-testable without a model)
# --------------------------------------------------------------------------- #
def trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    """Shrink [start, end) inward past leading/trailing whitespace & punctuation."""
    while start < end and text[start] in _EDGE_CHARS:
        start += 1
    while end > start and text[end - 1] in _EDGE_CHARS:
        end -= 1
    return start, end


def _priority(entity: Entity) -> tuple:
    # Lower sorts first / wins: deterministic before NER, then higher score,
    # then longer span, then earlier position.
    deterministic = 0 if entity.entity_type in DETERMINISTIC_ENTITIES else 1
    return (deterministic, -entity.score, -(entity.end - entity.start), entity.start)


def resolve_overlaps(entities: list[Entity]) -> list[Entity]:
    """Greedy non-overlap selection; deterministic detectors win over NER."""
    chosen: list[Entity] = []
    for entity in sorted(entities, key=_priority):
        if any(entity.start < c.end and c.start < entity.end for c in chosen):
            continue
        chosen.append(entity)
    return sorted(chosen, key=lambda e: e.start)


# --------------------------------------------------------------------------- #
# Per-line analysis with global offset mapping
# --------------------------------------------------------------------------- #
def analyze_document(
    doc: ExtractedDoc,
    engine,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    entities: list[str] | None = None,
) -> list[Entity]:
    """Analyze each line independently, then map results to global text offsets.

    `engine` is anything with an `.analyze(text, language, entities, score_threshold)`
    method returning objects that have `.entity_type`, `.start`, `.end`, `.score`
    (Presidio's AnalyzerEngine, or a stub in tests).
    """
    resolved: list[Entity] = []
    offset = 0
    for line in doc.lines:
        line_text = line.text
        raw = engine.analyze(
            text=line_text,
            language="en",
            entities=entities,
            score_threshold=score_threshold,
        )
        line_entities: list[Entity] = []
        for r in raw:
            start, end = trim_span(line_text, r.start, r.end)
            if start >= end:
                continue
            line_entities.append(
                Entity(
                    entity_type=r.entity_type,
                    start=start,
                    end=end,
                    score=float(r.score),
                    text=line_text[start:end],
                    source=line.source,
                )
            )
        for e in resolve_overlaps(line_entities):
            resolved.append(
                Entity(
                    entity_type=e.entity_type,
                    start=e.start + offset,
                    end=e.end + offset,
                    score=e.score,
                    text=e.text,
                    source=e.source,
                )
            )
        offset += len(line_text) + 1  # +1 for the "\n" that joins lines in .text
    return resolved
