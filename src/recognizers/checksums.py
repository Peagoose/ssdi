"""Pure checksum / structural-validity functions for structured PII numbers.

Kept dependency-free and separately testable. Each returns a plain bool so the
Presidio recognizers can wire them into `validate_result` (True -> score 1.0,
False -> the match is dropped). Real math only — no shortcuts.
"""
from __future__ import annotations

import re

_DIGITS = re.compile(r"\D")


def only_digits(value: str) -> str:
    """Strip everything that is not a digit."""
    return _DIGITS.sub("", value)


# --------------------------------------------------------------------------- #
# Luhn (credit cards; also useful for tests even though Presidio ships a card
# recognizer we reuse)
# --------------------------------------------------------------------------- #
def luhn_valid(value: str) -> bool:
    digits = only_digits(value)
    if len(digits) < 12 or len(digits) > 19:
        return False
    total = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


# --------------------------------------------------------------------------- #
# ABA routing number (US bank routing / RTN) — real checksum + prefix range
# --------------------------------------------------------------------------- #
# The first two digits (Federal Reserve routing symbol) must fall in an assigned
# range; this weeds out random 9-digit numbers that pass the weighted checksum.
_ABA_VALID_PREFIXES = set(
    list(range(0, 13))      # 00-12  Federal Reserve / government
    + list(range(21, 33))   # 21-32  thrift institutions
    + list(range(61, 73))   # 61-72  electronic transactions
    + [80]                  # 80     traveler's checks
)


def aba_routing_valid(value: str) -> bool:
    """True iff `value`'s digits form a valid ABA routing number.

    Weighted mod-10 checksum: 3*(d1+d4+d7) + 7*(d2+d5+d8) + (d3+d6+d9) == 0 (mod 10),
    plus the routing-symbol prefix must be in an assigned range.
    """
    d = only_digits(value)
    if len(d) != 9:
        return False
    prefix = int(d[:2])
    if prefix not in _ABA_VALID_PREFIXES:
        return False
    n = [int(x) for x in d]
    checksum = (
        3 * (n[0] + n[3] + n[6])
        + 7 * (n[1] + n[4] + n[7])
        + 1 * (n[2] + n[5] + n[8])
    )
    return checksum % 10 == 0


# --------------------------------------------------------------------------- #
# US SSN — structural validity per SSA rules (SSNs have no checksum digit)
# --------------------------------------------------------------------------- #
def ssn_structurally_valid(value: str) -> bool:
    """True iff digits form a structurally valid SSN (AAA-GG-SSSS).

    Invalid: area 000 / 666 / 900-999; group 00; serial 0000. These blocks are
    never issued, so rejecting them cuts false positives without a checksum.
    """
    d = only_digits(value)
    if len(d) != 9:
        return False
    area, group, serial = int(d[:3]), int(d[3:5]), int(d[5:])
    if area == 0 or area == 666 or area >= 900:
        return False
    if group == 0:
        return False
    if serial == 0:
        return False
    return True


# --------------------------------------------------------------------------- #
# US EIN — no checksum; validity is the assigned 2-digit campus prefix
# --------------------------------------------------------------------------- #
# IRS prefixes that have never been assigned to any campus. Everything else in
# 01-99 is (or has been) valid. Source: IRS "Valid EIN Prefixes" listing.
_EIN_INVALID_PREFIXES = {0, 7, 8, 9, 17, 18, 19, 28, 29, 49, 69, 70, 78, 79, 89, 96, 97}


def ein_prefix_valid(value: str) -> bool:
    """True iff the EIN's 2-digit prefix is an assigned IRS campus prefix."""
    d = only_digits(value)
    if len(d) != 9:
        return False
    return int(d[:2]) not in _EIN_INVALID_PREFIXES
