"""Credit card recognizer — REUSE Presidio's built-in CreditCardRecognizer.

Presidio already ships a Luhn-validated CREDIT_CARD recognizer, so we do not
reimplement it (golden rule: reuse battle-tested detection). This thin factory
exists only so the custom-recognizer registry has one obvious place to get it,
and so the layout in CLAUDE.md is honoured. Luhn logic itself is unit-tested in
checksums.py to prove the checksum path is genuine.
"""
from __future__ import annotations

from presidio_analyzer.predefined_recognizers import CreditCardRecognizer

CARD_ENTITY = "CREDIT_CARD"


def build_card_recognizer() -> CreditCardRecognizer:
    return CreditCardRecognizer()
