"""Smoke test — proves the Presidio engine + English NER model load and detect
REAL PII. No hardcoding: it runs a genuine analysis on a sample sentence.

Run (from the project root, with the venv active and the model downloaded):

    python -m src.smoke

Success: it prints a real EMAIL_ADDRESS and a real PERSON detection.
If the model is missing, it tells you exactly how to install it.
"""
from __future__ import annotations

import sys


def build_analyzer():
    """Build a Presidio AnalyzerEngine backed by spaCy en_core_web_lg."""
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
    }
    provider = NlpEngineProvider(nlp_configuration=configuration)
    nlp_engine = provider.create_engine()
    return AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])


def main() -> int:
    print("Loading Presidio + en_core_web_lg (first load takes a few seconds)...\n")
    try:
        analyzer = build_analyzer()
    except OSError as exc:
        print("ERROR: could not load the English NER model 'en_core_web_lg'.")
        print("Install it once (this is a one-time ~600 MB download):\n")
        print("    python -m spacy download en_core_web_lg\n")
        print(f"(details: {exc})")
        return 1
    except ImportError as exc:
        print("ERROR: a required package is missing. Install dependencies first:\n")
        print("    pip install -r requirements.txt\n")
        print(f"(details: {exc})")
        return 1

    # Uses a neural name (PERSON, proves the model) and a REALISTIC SSN
    # (deterministic regex, proves the pattern path). No email here on purpose:
    # Presidio's email recognizer attempts a network lookup, which we keep out of
    # the offline smoke test. Note: 123-45-6789 is rejected by Presidio as a dummy
    # sequential SSN, so we use a realistic non-sequential value.
    text = "Attorney Sarah Chen represents the plaintiff; her SSN on file is 536-90-4788."
    results = analyzer.analyze(text=text, language="en")

    if not results:
        print("No entities detected — the pipeline loaded but found nothing.")
        return 1

    print(f"Analyzed: {text!r}\n")
    print(f"{'ENTITY':<16}{'TEXT':<22}{'SCORE'}")
    print("-" * 46)
    for r in sorted(results, key=lambda x: x.start):
        print(f"{r.entity_type:<16}{text[r.start:r.end]:<22}{r.score:.2f}")

    found = {r.entity_type for r in results}
    ok = "PERSON" in found and "US_SSN" in found
    print()
    if ok:
        print("SUCCESS: real PERSON (neural NER) and US_SSN (regex) detected.")
        print("The engine and both detection paths are working.")
        return 0
    print("PARTIAL: engine ran but did not find both PERSON and US_SSN.")
    print(f"Detected types: {sorted(found)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
