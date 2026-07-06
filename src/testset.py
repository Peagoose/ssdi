"""Generate a LABELED synthetic legal test set (fake PII) for recall measurement.

Every value here is synthetic but realistic so the detectors behave as they would
on real documents:
  * SSNs are non-sequential and structurally valid (Presidio rejects dummies).
  * Routing numbers pass the real ABA checksum (public bank RTNs).
  * EIN prefixes are IRS-assigned; credit cards pass Luhn.
  * Dockets use the federal CM-ECF format; the bar number carries NY context.

Includes a TABLE-HEAVY workbook (parties.xlsx) — the key stress case for recall.

`generate_labeled_set(out_dir)` writes the files and returns a list of LabeledDoc,
each with the ground-truth (entity_type, value) pairs it contains.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LabeledDoc:
    path: Path
    entities: list[tuple[str, str]] = field(default_factory=list)


# Ground-truth people/orgs/locations (measured via NER on Windows).
_PARTIES = [
    ("Sarah Chen", "536-90-4788", "03/14/1985", "(212) 555-0182", "021000021"),
    ("Robert Alvarez", "457-55-1462", "11/02/1979", "(718) 555-0147", "011000015"),
    ("Maria Gomez", "212-09-9997", "07/23/1990", "(917) 555-0193", "121000248"),
    ("James O'Brien", "504-22-3311", "01/09/1968", "(646) 555-0110", "026009593"),
]


# --------------------------------------------------------------------------- #
# 1) Contract (Word) — prose PII
# --------------------------------------------------------------------------- #
def _make_contract(path: Path) -> LabeledDoc:
    from docx import Document

    doc = Document()
    doc.add_heading("CONSULTING SERVICES AGREEMENT", level=1)
    lines = [
        "This Agreement is entered into by Sarah Chen and Acme Holdings LLC.",
        "The Consultant's email is sarah.chen@example.com and phone (212) 555-0182.",
        "Consultant SSN: 536-90-4788. Employer EIN: 13-1234567.",
        "Payment to bank routing number 021000021, account 000123456789.",
        "Company card on file: 4111 1111 1111 1111.",
        "Consultant DOB: 03/14/1985. Address: 123 Main Street, New York, NY.",
    ]
    for ln in lines:
        doc.add_paragraph(ln)
    doc.save(str(path))
    return LabeledDoc(
        path=path,
        entities=[
            ("PERSON", "Sarah Chen"), ("ORG", "Acme Holdings LLC"),
            ("EMAIL_ADDRESS", "sarah.chen@example.com"),
            ("PHONE_NUMBER", "(212) 555-0182"),
            ("US_SSN", "536-90-4788"), ("US_EIN", "13-1234567"),
            ("US_BANK_ROUTING", "021000021"),
            ("CREDIT_CARD", "4111 1111 1111 1111"),
            ("US_DOB", "03/14/1985"),
            ("LOCATION", "123 Main Street"),
        ],
    )


# --------------------------------------------------------------------------- #
# 2) Pleading (PDF) — court caption
# --------------------------------------------------------------------------- #
def _make_pleading(path: Path) -> LabeledDoc:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    t = c.beginText(72, 720)
    for ln in [
        "UNITED STATES DISTRICT COURT",
        "SOUTHERN DISTRICT OF NEW YORK",
        "SARAH CHEN, Plaintiff,",
        "v.                              Case No. 1:21-cv-01234",
        "ACME HOLDINGS LLC, Defendant.",
        "Before the Honorable Alison Nathan.",
        "Counsel: Robert Alvarez, Bar No. 4567890.",
        "Plaintiff email: sarah.chen@example.com.",
    ]:
        t.textLine(ln)
    c.drawText(t)
    c.showPage()
    c.save()
    return LabeledDoc(
        path=path,
        entities=[
            ("US_COURT_DOCKET", "1:21-cv-01234"),
            ("PERSON", "Alison Nathan"), ("PERSON", "Robert Alvarez"),
            ("US_BAR_NUMBER", "4567890"),
            ("EMAIL_ADDRESS", "sarah.chen@example.com"),
        ],
    )


# --------------------------------------------------------------------------- #
# 3) Parties workbook (Excel) — TABLE-HEAVY (the key recall stress test)
# --------------------------------------------------------------------------- #
def _make_parties(path: Path) -> LabeledDoc:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Parties"
    ws.append(["Name", "SSN", "DOB", "Phone", "Routing"])
    entities: list[tuple[str, str]] = []
    for name, ssn, dob, phone, routing in _PARTIES:
        ws.append([name, ssn, dob, phone, routing])
        entities += [
            ("PERSON", name), ("US_SSN", ssn), ("US_DOB", dob),
            ("PHONE_NUMBER", phone), ("US_BANK_ROUTING", routing),
        ]
    wb.save(str(path))
    return LabeledDoc(path=path, entities=entities)


def generate_labeled_set(out_dir: str | Path) -> list[LabeledDoc]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return [
        _make_contract(out_dir / "contract.docx"),
        _make_pleading(out_dir / "pleading.pdf"),
        _make_parties(out_dir / "parties.xlsx"),
    ]
