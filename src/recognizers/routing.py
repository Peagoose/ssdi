"""US bank routing number (ABA RTN) recognizer — real weighted checksum.

Presidio's built-in US_BANK_NUMBER is a loose 8-17 digit match with NO checksum.
A routing number is exactly 9 digits with a well-defined mod-10 checksum, so we
detect it deterministically: a 9-digit run whose checksum (and assigned prefix)
validates is scored 1.0; anything failing the checksum is dropped entirely.
"""
from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from .checksums import aba_routing_valid

ROUTING_ENTITY = "US_BANK_ROUTING"


class RoutingNumberRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        patterns = [
            Pattern(name="routing-9", regex=r"\b\d{9}\b", score=0.2),
        ]
        super().__init__(
            supported_entity=ROUTING_ENTITY,
            patterns=patterns,
            context=["routing", "aba", "rtn", "routing number", "aba number"],
        )

    def validate_result(self, pattern_text: str):
        # Checksum is authoritative: valid -> 1.0, invalid -> dropped.
        return aba_routing_valid(pattern_text)
