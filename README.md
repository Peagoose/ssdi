# Legal PII Anonymizer

A **local, offline** desktop tool that finds and redacts personal information (PII)
in English-language legal documents (**PDF, Word, Excel**), replacing each value with
a typed, reversible placeholder (`[NAME_1]`, `[SSN_1]`) or a court-style partial mask
(`XXX-XX-4788`), and giving you back the anonymized file plus a separate
re-identification key.

> Assists **FRCP 5.2** compliance but is **not legal advice**. Every output must be
> verified by a human before filing.

Detection is **genuine** — real regex + checksums for structured numbers (SSN, EIN,
ABA routing, credit card, IBAN), and real neural NER (spaCy `en_core_web_lg`) for
names, organizations, and locations. Nothing is faked, and after the one-time model
download nothing touches the network.

---

## Setup (Windows, one time)

Open **PowerShell** in the project folder and run:

```powershell
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_lg
```

The last line downloads the English model once (~600 MB). After that the tool is
fully offline.

## Run the app

```powershell
venv\Scripts\activate
streamlit run src/app.py
```

Your browser opens the app. Upload a PDF, Word, or Excel file and you'll see:
- the text with PII **highlighted by type**,
- an **anonymized** view (toggle to reveal originals),
- a **per-type count** summary,
- **download** buttons for the anonymized file and the CSV key,
- a **sidebar** to configure the FRCP 5.2 redaction rules.

## Check the engine works

```powershell
python -m src.smoke
```

Prints a real detection (a name via NER and an SSN via regex).

## Measure detection quality

```powershell
python -m src.measure
```

Generates a labeled synthetic test set (including a **table-heavy** workbook) and
writes per-type recall/precision to `results/recall.csv`.

## Run the tests (developers)

```powershell
pip install pytest
python -m pytest
```

---

## What it detects
Names, organizations, locations/addresses (NER) · SSN · EIN · ABA bank routing
(checksum) · credit card (Luhn) · IBAN (mod-97) · US bank account · driver license ·
passport · email · phone · date of birth · federal court docket numbers · NY attorney
registration (bar) numbers.

## How it's built
See `CLAUDE.md` for the architecture and the golden rules, and `TASKS.md` for the
task-by-task build log. Core stack: Microsoft Presidio (analyzer + anonymizer),
spaCy, pdfplumber / python-docx / openpyxl, PyMuPDF, Streamlit.

## Scope of this build
Docket numbers = federal CM-ECF (covers S.D.N.Y. / E.D.N.Y.). Bar numbers = NY
attorney registration. This is a proof-of-concept spike, not production software.
