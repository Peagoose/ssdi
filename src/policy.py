"""FRCP 5.2 legal redaction policy — configurable partial masking.

Federal court filing rules (FRCP 5.2 / equivalents) don't fully hide certain
values; they partially redact them:
  * SSN / taxpayer ID     -> last 4 digits         "XXX-XX-4788"
  * Financial account #s  -> last 4 digits         "****4788"
  * Dates of birth        -> year only             "1985"
  * Names of minors       -> initials              "R.A."
  * Home addresses        -> redacted

This module renders those masks. Each rule is a mode so the UI settings panel can
toggle between the legal partial mask and a fully-reversible placeholder.

IMPORTANT (honesty): distinguishing a *minor's* name from an adult's, or a *home*
address from a city, cannot be done reliably by detection alone. So:
  * minors -> initials is provided as a MECHANISM and applied only when a name is
    explicitly flagged (entity type PERSON_MINOR); it is NOT auto-inferred here.
  * address redaction acts on LOCATION/GPE entities the model already found.
The tool assists compliance; a human must verify output before filing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .recognizers import (
    CARD_ENTITY,
    DOB_ENTITY,
    IBAN_ENTITY,
    SSN_ENTITY,
)

# Entity types this policy governs, grouped by rule.
_TAXPAYER_TYPES = {SSN_ENTITY, "US_ITIN"}
_FINANCIAL_TYPES = {CARD_ENTITY, IBAN_ENTITY, "US_BANK_NUMBER"}
_DOB_TYPES = {DOB_ENTITY}
_ADDRESS_TYPES = {"LOCATION", "GPE"}
_MINOR_TYPES = {"PERSON_MINOR"}

_NON_DIGIT = re.compile(r"\D")
_YEAR = re.compile(r"\b(\d{4})\b")


# --------------------------------------------------------------------------- #
# Pure mask transforms (unit-testable)
# --------------------------------------------------------------------------- #
def mask_ssn_last4(value: str) -> str:
    """'536-90-4788' -> 'XXX-XX-4788' (keep the SSN's visual shape)."""
    digits = _NON_DIGIT.sub("", value)
    if len(digits) < 4:
        return "XXX-XX-XXXX"
    return f"XXX-XX-{digits[-4:]}"


def mask_account_last4(value: str) -> str:
    """Any account/card/IBAN -> '****<last4>'."""
    digits = _NON_DIGIT.sub("", value)
    if len(digits) < 4:
        return "****"
    return f"****{digits[-4:]}"


def dob_to_year(value: str) -> str | None:
    """Reduce a birth date to its 4-digit year, or None if no year is present."""
    m = _YEAR.search(value)
    return m.group(1) if m else None


def name_to_initials(value: str) -> str:
    """'Robert Alvarez' -> 'R.A.'  ; 'Mary Beth Chen' -> 'M.B.C.'"""
    parts = [p for p in re.split(r"\s+", value.strip()) if p]
    initials = [p[0].upper() for p in parts if p[0].isalpha()]
    return ".".join(initials) + "." if initials else value


# --------------------------------------------------------------------------- #
# Policy
# --------------------------------------------------------------------------- #
@dataclass
class RedactionPolicy:
    """Configurable FRCP-style policy. Defaults follow FRCP 5.2.

    Each mode is either the legal partial mask or "placeholder" (fall back to the
    fully-reversible [PREFIX_n] token).
    """
    ssn: str = "last4"          # "last4" | "placeholder"
    financial: str = "last4"    # "last4" | "placeholder"
    dob: str = "year"           # "year"  | "placeholder"
    address: str = "redact"     # "redact" | "placeholder"
    minors: str = "initials"    # "initials" | "placeholder"

    def render(self, entity_type: str, value: str) -> str | None:
        """Return the masked token for a governed entity, or None to use the
        default reversible placeholder."""
        if entity_type in _TAXPAYER_TYPES and self.ssn == "last4":
            return mask_ssn_last4(value)
        if entity_type in _FINANCIAL_TYPES and self.financial == "last4":
            return mask_account_last4(value)
        if entity_type in _DOB_TYPES and self.dob == "year":
            year = dob_to_year(value)
            return year if year is not None else None
        if entity_type in _ADDRESS_TYPES and self.address == "redact":
            return "[ADDRESS_REDACTED]"
        if entity_type in _MINOR_TYPES and self.minors == "initials":
            return name_to_initials(value)
        return None


def frcp_default() -> RedactionPolicy:
    """The default federal-court redaction policy."""
    return RedactionPolicy()


def full_placeholder_policy() -> RedactionPolicy:
    """Everything becomes a fully-reversible placeholder (no partial masks)."""
    return RedactionPolicy(
        ssn="placeholder",
        financial="placeholder",
        dob="placeholder",
        address="placeholder",
        minors="placeholder",
    )
