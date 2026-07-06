"""IBAN recognizer — REUSE Presidio's built-in IbanRecognizer.

Presidio's IbanRecognizer already implements the ISO 13616 mod-97 checksum, so
we reuse it rather than reimplement. Thin factory for the registry; see CLAUDE.md.
"""
from __future__ import annotations

from presidio_analyzer.predefined_recognizers import IbanRecognizer

IBAN_ENTITY = "IBAN_CODE"


def build_iban_recognizer() -> IbanRecognizer:
    return IbanRecognizer()
