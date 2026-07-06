# TASKS — Legal PII Anonymizer (spike)

Work through these **in order, one at a time**. Each task shows a **success check**
that must pass before moving on. Real detection only — never fake, hardcode, or
simulate a result.

Status legend: `[ ]` todo · `[~]` in progress · `[x]` done

---

## [x] Task 1 — Project scaffold + smoke test
Folder structure, `requirements.txt`, `TASKS.md`, `CLAUDE.md`, `.gitignore`, and a
smoke test that loads the Presidio engine + `en_core_web_lg` and detects real PII.
- **Success check:** `python -m src.smoke` prints a real `EMAIL_ADDRESS` and `PERSON`
  detection (requires the model download to have been run once).

## [x] Task 2 — File extraction (`src/extract.py`)
PDF (pdfplumber), Word (python-docx), Excel (openpyxl) → clean text, preserving
line/cell boundaries so detection can run per line.
- **Success check:** extract each of the 3 sample formats and print line-preserved text.

## [x] Task 3 — Custom recognizers (`src/recognizers/`)
SSN, EIN, ABA routing (+checksum), credit card & IBAN (reuse Presidio), federal
CM-ECF docket, NY attorney registration (bar) number. Deterministic + high score.
- **Success check:** `pytest tests/test_recognizers.py` — valid numbers detected,
  invalid checksums rejected.

## [x] Task 4 — Analysis pipeline (`src/analyze.py`)
Presidio + spaCy, **per-line** NER, overlap resolution (deterministic beats NER),
whitespace/punctuation span trimming.
- **Success check:** a mixed line ("SSN 123-45-6789 for John Smith") yields SSN from
  the regex recognizer (not NER) and PERSON for the name, spans trimmed exactly.

## [x] Task 5 — Anonymization + key (`src/anonymize.py`)
Typed reversible placeholders `[NAME_1]`; same surface value → same placeholder;
numbers assigned in reading order; CSV re-identification key.
- **Success check:** repeated value gets one placeholder; key round-trips to original.

## [x] Task 6 — Legal redaction policy (FRCP 5.2)
Configurable: SSN→last4, financial accounts→last4, minors→initials, DOB→year,
addresses→redact. Settings toggles.
- **Success check:** toggling policy changes output as specified; default = FRCP.

## [x] Task 7 — File output + PDF redaction
`src/anonymize_files.py` (docx/xlsx) and `src/redact_pdf.py` — in-place redaction,
tight contiguous-run matching within one (block,line), font-fit placeholders.
- **Success check:** redacted PDF has original values truly removed (text search finds
  none) and placeholders land on the correct cells.

## [x] Task 8 — Streamlit UI (`src/app.py`)
Upload, color-coded highlight view, toggle to anonymized, click-to-reveal, per-type
count summary, download buttons up top, calm custom CSS.
- **Success check:** `streamlit run src/app.py`, upload a sample, see highlights +
  anonymized view + counts + downloads.

## [ ] Task 9 — Recall measurement + test set
Generate labeled synthetic test set incl. a **table-heavy** document; measure
recall/precision per entity type; write to `results/`.
- **Success check:** `python -m src.measure` writes a per-type recall report.

---

### Jurisdiction decisions (from the user)
- Docket numbers: **Federal CM-ECF** format (covers S.D.N.Y. and E.D.N.Y.).
- Bar numbers: **NY attorney registration** (7-digit) format.

### Findings log (verified by real runs, keep updating)
- Presidio 2.2.363 installs cleanly on Python 3.11; real detection confirmed
  (email 1.00, realistic SSN 0.5).
- **Presidio rejects sequential/dummy SSNs** (e.g. `123-45-6789` → invalidated).
  Synthetic test data (Task 9) MUST use realistic non-sequential numbers like
  `536-90-4788`.
- **`EmailRecognizer` attempts a network call** to publicsuffix.org (falls back to a
  bundled snapshot). Task 4 must force tldextract offline so the tool is truly offline
  and produces no console noise.

### Environment notes
- Dev happens in a Linux cloud container (code + unit tests). The spaCy model
  download, the Streamlit UI, and PDF rendering are run by the user on **Windows**.
