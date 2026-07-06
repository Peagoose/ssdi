"""Tests for custom recognizers + checksums.

Proves REAL detection: valid numbers are found and scored high, and numbers that
fail their checksum / structure are rejected (not merely low-scored). Recognizers
are exercised directly (nlp_artifacts=None) so these tests need no NER model.
"""
from __future__ import annotations

import pytest

from src.recognizers.checksums import (
    aba_routing_valid,
    ein_prefix_valid,
    luhn_valid,
    ssn_structurally_valid,
)
from src.recognizers.ssn import SsnRecognizer, SSN_ENTITY
from src.recognizers.ein import EinRecognizer, EIN_ENTITY
from src.recognizers.routing import RoutingNumberRecognizer, ROUTING_ENTITY
from src.recognizers.docket import DocketRecognizer, DOCKET_ENTITY
from src.recognizers.bar_number import NyBarNumberRecognizer, BAR_ENTITY


def _scores(recognizer, text, entity):
    res = recognizer.analyze(text, entities=[entity], nlp_artifacts=None)
    return {(text[r.start:r.end]): r.score for r in res}


# --------------------------------------------------------------------------- #
# Pure checksums
# --------------------------------------------------------------------------- #
def test_luhn():
    assert luhn_valid("4111 1111 1111 1111")   # valid Visa test number
    assert not luhn_valid("4111 1111 1111 1112")  # last digit broken


def test_aba_routing_checksum():
    assert aba_routing_valid("021000021")   # JPMorgan Chase (valid, real bank RTN)
    assert aba_routing_valid("011000015")   # FRB Boston
    assert not aba_routing_valid("021000022")  # broken check digit
    assert not aba_routing_valid("999999999")  # bad prefix + checksum


def test_ssn_structure():
    assert ssn_structurally_valid("536-90-4788")
    assert not ssn_structurally_valid("000-12-3456")  # area 000
    assert not ssn_structurally_valid("666-12-3456")  # area 666
    assert not ssn_structurally_valid("900-12-3456")  # area >= 900
    assert not ssn_structurally_valid("536-00-4788")  # group 00
    assert not ssn_structurally_valid("536-90-0000")  # serial 0000


def test_ein_prefix():
    assert ein_prefix_valid("13-1234567")   # 13 assigned
    assert not ein_prefix_valid("07-1234567")  # 07 never assigned


# --------------------------------------------------------------------------- #
# SSN recognizer
# --------------------------------------------------------------------------- #
def test_ssn_dashed_detected_high():
    scores = _scores(SsnRecognizer(), "Her SSN is 536-90-4788 on file.", SSN_ENTITY)
    assert scores.get("536-90-4788") == 1.0  # structurally valid -> validated to 1.0


def test_ssn_invalid_area_rejected():
    # area 000 is structurally invalid -> must be dropped, not returned
    scores = _scores(SsnRecognizer(), "SSN 000-12-3456 here", SSN_ENTITY)
    assert "000-12-3456" not in scores


def test_ssn_bare_is_low_without_context():
    # bare 9 digits: ambiguous, kept only at low base score (context would boost)
    scores = _scores(SsnRecognizer(), "value 536904788 end", SSN_ENTITY)
    assert scores.get("536904788", 0) <= 0.3


# --------------------------------------------------------------------------- #
# EIN recognizer
# --------------------------------------------------------------------------- #
def test_ein_valid_prefix_detected():
    scores = _scores(EinRecognizer(), "EIN 13-1234567", EIN_ENTITY)
    assert scores.get("13-1234567") == 1.0


def test_ein_invalid_prefix_rejected():
    scores = _scores(EinRecognizer(), "EIN 07-1234567", EIN_ENTITY)
    assert "07-1234567" not in scores


# --------------------------------------------------------------------------- #
# Routing recognizer (checksum is authoritative)
# --------------------------------------------------------------------------- #
def test_routing_valid_checksum_detected():
    scores = _scores(RoutingNumberRecognizer(), "routing 021000021", ROUTING_ENTITY)
    assert scores.get("021000021") == 1.0


def test_routing_bad_checksum_rejected():
    scores = _scores(RoutingNumberRecognizer(), "routing 021000022", ROUTING_ENTITY)
    assert "021000022" not in scores


# --------------------------------------------------------------------------- #
# Docket recognizer
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("docket", ["1:21-cv-01234", "7:19-cr-00456-ABC", "2:22-cv-00987-JGK-RML"])
def test_docket_detected(docket):
    scores = _scores(DocketRecognizer(), f"Case No. {docket} (S.D.N.Y.)", DOCKET_ENTITY)
    assert docket in scores and scores[docket] >= 0.85


def test_docket_non_docket_not_matched():
    scores = _scores(DocketRecognizer(), "Please call 212-555-0182 today", DOCKET_ENTITY)
    assert scores == {}


# --------------------------------------------------------------------------- #
# NY bar number recognizer (needs context to be meaningful)
# --------------------------------------------------------------------------- #
def test_bar_number_detected_with_context():
    res = NyBarNumberRecognizer().analyze(
        "Attorney registration number 4567890", entities=[BAR_ENTITY], nlp_artifacts=None
    )
    assert any("4567890" == "Attorney registration number 4567890"[r.start:r.end] for r in res)
