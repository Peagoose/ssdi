# CLAUDE.md — Legal PII Anonymizer

A **local, offline** desktop tool that anonymizes PII in English-language legal
documents (PDF / Word / Excel). Upload a file → every PII entity is detected and
replaced with a typed, reversible placeholder (`[NAME_1]`, `[SSN_1]`) → download the
anonymized file plus a separate re-identification key. This is a **spike** answering:
does PII detection work well enough on real legal English, including tables?

## Golden rules (do not break)
1. **Real detection only.** Never simulate, hardcode, or fake a result. Structured
   numbers use real regex + checksum; names use real neural NER. If something can't be
   detected, say so honestly.
2. **Fully local.** No cloud, no Docker, no external API, no LLM calls. Offline after
   the one-time `en_core_web_lg` download.
3. **Deterministic numbers beat NER.** SSN/EIN/credit card/routing/IBAN/phone are found
   by regex (+checksum where one exists). On any overlap, the deterministic detector
   wins over the NER model.
4. **Plan before code; one task at a time.** See `TASKS.md`. Show each task's success
   check before moving on.
5. **No real PII in the repo.** Test data is synthetic, under `test_files/`.

## Known traps (baked-in lessons)
- Run NER **per line**, not on the whole document — tables with numbers between rows
  wreck recall otherwise.
- Same surface value → same placeholder within a document; number placeholders in
  reading order so the key is stable.
- Trim whitespace/punctuation from NER span edges.
- PDF redaction: match each value as a **tight contiguous run** of words inside one
  `(block_no, line_no)` group — never a page-wide union of look-alike words. Numbers
  match by EXACT concatenated digits of the run. Fit placeholder font to the cleared box.
- The PDF's detection must run on the SAME text shown on screen.

## Tech stack
Python 3.11+ · Presidio (analyzer + anonymizer) · spaCy `en_core_web_lg` (CPU) ·
pdfplumber / python-docx / openpyxl · PyMuPDF (fitz) for PDF redaction · Streamlit UI.

## Layout
```
src/
  recognizers/   custom: ssn, ein, routing, iban, card, docket, bar_number
  extract.py     file -> clean text (pdf/docx/xlsx)
  analyze.py     Presidio + English NER, per-line, overlap resolution
  anonymize.py   entities -> typed placeholders (+ CSV key)
  redact_pdf.py  in-place PDF redaction
  anonymize_files.py  docx/xlsx anonymization
  app.py         Streamlit UI
  smoke.py       engine load + detection smoke test
tests/           unit tests (recognizers, checksums, pipeline)
test_files/      synthetic docs with fake PII
results/         recall measurement output
```

## Legal redaction standard
Default policy follows US federal court rules (FRCP 5.2), configurable in a settings
panel: SSN→last 4, financial accounts→last 4, minors→initials, DOB→year, home
addresses redacted. **Assists compliance but is not legal advice; output must be
verified by a human before filing.**

## Jurisdiction scope (this build)
Docket = Federal CM-ECF (covers S.D.N.Y. / E.D.N.Y.). Bar = NY attorney registration.

## Dev / run
- Dev + unit tests run in a Linux container. The **model download, Streamlit UI, and
  PDF rendering are run by the user on Windows** (see `README`/setup commands).
- Setup: `python -m venv venv` → `venv\Scripts\activate` → `pip install -r requirements.txt`
  → `python -m spacy download en_core_web_lg`.
- Smoke test: `python -m src.smoke`. UI: `streamlit run src/app.py`.
