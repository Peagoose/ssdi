"""Federal court docket / case number recognizer (CM-ECF / PACER format).

Covers the standard federal pattern used by S.D.N.Y. and E.D.N.Y.:

    {office}:{yy}-{type}-{number}[-{judge initials}][-{magistrate initials}]
    e.g.  1:21-cv-01234        7:19-cr-00456-ABC        2:22-cv-00987-JGK-RML

The shape is distinctive enough to score highly on its own; context words
("case", "docket", "civil action") give an extra boost.
"""
from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

DOCKET_ENTITY = "US_COURT_DOCKET"

# office ':' 2-digit-year '-' case-type '-' 4to6-digit-number, then up to two
# optional groups of judge/magistrate initials.
_CASE_TYPES = r"cv|cr|mc|mj|md|bk|cm|po|gd|mdl"
_DOCKET_REGEX = (
    r"\b\d:\d{2}-(?:" + _CASE_TYPES + r")-\d{4,6}"
    r"(?:-[A-Za-z]{1,4}){0,2}\b"
)


class DocketRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        patterns = [
            Pattern(name="cm-ecf-docket", regex=_DOCKET_REGEX, score=0.85),
        ]
        super().__init__(
            supported_entity=DOCKET_ENTITY,
            patterns=patterns,
            context=["case", "docket", "civil action", "criminal action",
                     "no.", "index no", "case no"],
        )  # default flags include IGNORECASE, so 'cv' also matches 'CV'
