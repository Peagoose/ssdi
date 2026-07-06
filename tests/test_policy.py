"""Tests for src/policy.py (FRCP redaction) + integration with anonymize()."""
from __future__ import annotations

from src.analyze import Entity
from src.anonymize import anonymize
from src.policy import (
    RedactionPolicy,
    dob_to_year,
    frcp_default,
    full_placeholder_policy,
    mask_account_last4,
    mask_ssn_last4,
    name_to_initials,
)


# --------------------------------------------------------------------------- #
# Pure transforms
# --------------------------------------------------------------------------- #
def test_mask_ssn_last4():
    assert mask_ssn_last4("536-90-4788") == "XXX-XX-4788"
    assert mask_ssn_last4("536904788") == "XXX-XX-4788"


def test_mask_account_last4():
    assert mask_account_last4("4111 1111 1111 1111") == "****1111"
    assert mask_account_last4("GB33BUKB20201555555555") == "****5555"


def test_dob_to_year():
    assert dob_to_year("03/14/1985") == "1985"
    assert dob_to_year("March 14, 1985") == "1985"
    assert dob_to_year("no year here") is None


def test_name_to_initials():
    assert name_to_initials("Robert Alvarez") == "R.A."
    assert name_to_initials("Mary Beth Chen") == "M.B.C."


# --------------------------------------------------------------------------- #
# Policy.render dispatch
# --------------------------------------------------------------------------- #
def test_frcp_default_masks():
    p = frcp_default()
    assert p.render("US_SSN", "536-90-4788") == "XXX-XX-4788"
    assert p.render("CREDIT_CARD", "4111111111111111") == "****1111"
    assert p.render("US_DOB", "03/14/1985") == "1985"
    assert p.render("LOCATION", "123 Main St") == "[ADDRESS_REDACTED]"
    assert p.render("PERSON_MINOR", "Robert Alvarez") == "R.A."
    # A normal name is not governed -> falls back to placeholder
    assert p.render("PERSON", "Sarah Chen") is None


def test_placeholder_policy_disables_masks():
    p = full_placeholder_policy()
    assert p.render("US_SSN", "536-90-4788") is None
    assert p.render("US_DOB", "03/14/1985") is None


# --------------------------------------------------------------------------- #
# Integration with anonymize()
# --------------------------------------------------------------------------- #
def test_anonymize_applies_frcp_default():
    text = "Sarah Chen SSN 536-90-4788"
    ents = [
        Entity("PERSON", 0, 10, 1.0, "Sarah Chen"),
        Entity("US_SSN", 15, 26, 1.0, "536-90-4788"),
    ]
    result = anonymize(text, ents, policy=frcp_default())
    assert result.text == "[NAME_1] SSN XXX-XX-4788"
    # Redaction is still reversible: the key holds the full original
    ssn_row = next(r for r in result.key if r.entity_type == "US_SSN")
    assert ssn_row.original == "536-90-4788"
    assert ssn_row.placeholder == "XXX-XX-4788"


def test_anonymize_placeholder_mode_full_reversible():
    text = "SSN 536-90-4788"
    ents = [Entity("US_SSN", 4, 15, 1.0, "536-90-4788")]
    result = anonymize(text, ents, policy=full_placeholder_policy())
    assert result.text == "SSN [SSN_1]"


def test_dob_year_only_in_context_integration():
    text = "DOB 03/14/1985"
    ents = [Entity("US_DOB", 4, 14, 0.65, "03/14/1985")]
    result = anonymize(text, ents, policy=frcp_default())
    assert result.text == "DOB 1985"
