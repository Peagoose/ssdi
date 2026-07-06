"""Custom Presidio recognizers (deterministic regex + checksum detectors).

`custom_recognizers()` returns the recognizers this project ADDS on top of
Presidio's predefined set (SSN structure, EIN, ABA routing checksum, federal
docket, NY bar). `reused_recognizers()` returns Presidio's own checksummed
recognizers we deliberately REUSE (credit card, IBAN) instead of reimplementing.

`DETERMINISTIC_ENTITIES` lists the entity types that must win over NER on any
overlap (see analyze.py) — these come from regex/checksum, not the neural model.
"""
from __future__ import annotations

from presidio_analyzer import EntityRecognizer

from .bar_number import BAR_ENTITY, NyBarNumberRecognizer
from .card import CARD_ENTITY, build_card_recognizer
from .docket import DOCKET_ENTITY, DocketRecognizer
from .ein import EIN_ENTITY, EinRecognizer
from .iban import IBAN_ENTITY, build_iban_recognizer
from .routing import ROUTING_ENTITY, RoutingNumberRecognizer
from .ssn import SSN_ENTITY, SsnRecognizer


def custom_recognizers() -> list[EntityRecognizer]:
    """Recognizers we implement here."""
    return [
        SsnRecognizer(),
        EinRecognizer(),
        RoutingNumberRecognizer(),
        DocketRecognizer(),
        NyBarNumberRecognizer(),
    ]


def reused_recognizers() -> list[EntityRecognizer]:
    """Presidio's own checksummed recognizers we reuse as-is."""
    return [
        build_card_recognizer(),
        build_iban_recognizer(),
    ]


# Entities produced by deterministic regex/checksum detectors. On any span overlap
# with an NER entity (PERSON/ORG/LOCATION/DATE_TIME), these take precedence.
DETERMINISTIC_ENTITIES = frozenset(
    {
        SSN_ENTITY,
        EIN_ENTITY,
        ROUTING_ENTITY,
        DOCKET_ENTITY,
        BAR_ENTITY,
        CARD_ENTITY,
        IBAN_ENTITY,
        # Presidio predefined deterministic types we also treat as authoritative:
        "US_BANK_NUMBER",
        "US_DRIVER_LICENSE",
        "US_PASSPORT",
        "US_ITIN",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "IP_ADDRESS",
        "URL",
        "CRYPTO",
    }
)

__all__ = [
    "custom_recognizers",
    "reused_recognizers",
    "DETERMINISTIC_ENTITIES",
    "SSN_ENTITY",
    "EIN_ENTITY",
    "ROUTING_ENTITY",
    "DOCKET_ENTITY",
    "BAR_ENTITY",
    "CARD_ENTITY",
    "IBAN_ENTITY",
]
