"""Date-of-birth recognizer.

FRCP 5.2 redacts a DOB to the year only, but a bare date is just a date — we must
know it's a *birth* date. So this recognizer matches date-shaped strings at a low
base score that only survives when birth context ("DOB", "date of birth", "born")
is nearby. On a DOB line it outranks the generic DATE_TIME NER (US_DOB is in
DETERMINISTIC_ENTITIES), so the year-only policy can target it precisely; other
dates stay DATE_TIME.
"""
from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

DOB_ENTITY = "US_DOB"

_MONTHS = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)


class DobRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        patterns = [
            # 03/14/1985, 3-14-85, 1985/03/14
            Pattern(name="dob-numeric",
                    regex=r"\b\d{1,4}[/-]\d{1,2}[/-]\d{1,4}\b", score=0.3),
            # March 14, 1985  /  14 March 1985
            Pattern(name="dob-month-name",
                    regex=r"\b(?:" + _MONTHS + r")\.?\s+\d{1,2},?\s+\d{4}\b", score=0.3),
            Pattern(name="dob-day-month",
                    regex=r"\b\d{1,2}\s+(?:" + _MONTHS + r")\.?\s+\d{4}\b", score=0.3),
        ]
        super().__init__(
            supported_entity=DOB_ENTITY,
            patterns=patterns,
            context=["dob", "d.o.b", "date of birth", "born", "birth date",
                     "birthdate", "birthday"],
        )
