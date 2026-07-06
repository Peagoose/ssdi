"""US Social Security Number recognizer (deterministic, high-confidence).

SSNs carry no checksum, so we validate structure (SSA-invalid blocks) on the
clearly SSN-shaped dashed/spaced form and score it 1.0. A bare 9-digit run is
too ambiguous to claim as an SSN on shape alone, so it gets a low base score
that only survives when SSN context words ("SSN", "social security") are near.
"""
from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

from .checksums import ssn_structurally_valid

SSN_ENTITY = "US_SSN"


class SsnRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        patterns = [
            # AAA-GG-SSSS or AAA GG SSSS — unmistakably SSN-shaped.
            Pattern(name="ssn-dashed", regex=r"\b\d{3}[- ]\d{2}[- ]\d{4}\b", score=0.6),
            # Bare 9 digits — ambiguous; low base, leans on context to survive.
            Pattern(name="ssn-bare", regex=r"\b\d{9}\b", score=0.3),
        ]
        super().__init__(
            supported_entity=SSN_ENTITY,
            patterns=patterns,
            context=["ssn", "ssn#", "social security", "social security number", "soc sec"],
        )

    def validate_result(self, pattern_text: str):
        # Only assert validity for the dashed/spaced form. Returning True -> 1.0;
        # False -> dropped. For the bare form we return None (keep base 0.3) so a
        # random 9-digit number isn't over-claimed as an SSN without context.
        if any(sep in pattern_text for sep in ("-", " ")):
            return ssn_structurally_valid(pattern_text)
        return None
