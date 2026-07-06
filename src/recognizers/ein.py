"""US Employer Identification Number (EIN) recognizer.

EIN format is NN-NNNNNNN. There is no checksum, but the 2-digit prefix is an IRS
campus code and only certain prefixes are assigned — we validate against that set.
The dashed form with a valid prefix is scored 1.0; a bare 9-digit run relies on
context ("EIN", "employer identification", "federal tax id").
"""
from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from .checksums import ein_prefix_valid

EIN_ENTITY = "US_EIN"


class EinRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        patterns = [
            Pattern(name="ein-dashed", regex=r"\b\d{2}-\d{7}\b", score=0.6),
            Pattern(name="ein-bare", regex=r"\b\d{9}\b", score=0.2),
        ]
        super().__init__(
            supported_entity=EIN_ENTITY,
            patterns=patterns,
            context=[
                "ein", "e.i.n", "employer identification", "employer id",
                "federal tax id", "fein", "tax id", "taxpayer id", "tin",
            ],
        )

    def validate_result(self, pattern_text: str):
        if "-" in pattern_text:
            return ein_prefix_valid(pattern_text)
        return None
