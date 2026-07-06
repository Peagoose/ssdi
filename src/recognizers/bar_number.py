"""New York attorney registration ("bar") number recognizer.

NY attorney registration numbers are 7 digits. Seven bare digits are inherently
ambiguous, so the base score is low and detection leans on nearby context words
("bar", "registration", "attorney registration"). This is an honest limitation:
without context, a 7-digit number cannot be claimed as a bar number.
"""
from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

BAR_ENTITY = "US_BAR_NUMBER"


class NyBarNumberRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        patterns = [
            Pattern(name="ny-bar-7", regex=r"\b\d{7}\b", score=0.3),
        ]
        super().__init__(
            supported_entity=BAR_ENTITY,
            patterns=patterns,
            context=[
                "bar", "bar no", "bar number", "registration", "reg. no",
                "attorney registration", "registration number", "nys bar",
                "ny bar", "admitted",
            ],
        )
