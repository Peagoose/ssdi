"""Write anonymized Word (.docx) and Excel (.xlsx) files.

Strategy: because detected entities never span a line break, the anonymized text
(`Anonymization.text`) split on "\n" aligns 1:1 with `ExtractedDoc.lines`. Each
line carries a `source` tag (paragraph index / table cell / sheet cell), so we map
source -> anonymized line text and write it straight back to the right element,
leaving everything else untouched.
"""
from __future__ import annotations

from pathlib import Path

from .anonymize import Anonymization
from .extract import ExtractedDoc


def _source_to_text(doc: ExtractedDoc, anon: Anonymization) -> dict[str, str]:
    """Map each line's source tag to its anonymized text."""
    anon_lines = anon.text.split("\n")
    if len(anon_lines) != len(doc.lines):
        # Defensive: fall back to per-line count mismatch by zipping the shorter.
        anon_lines = anon_lines[: len(doc.lines)]
    return {line.source: anon_lines[i] for i, line in enumerate(doc.lines)}


# --------------------------------------------------------------------------- #
# Word
# --------------------------------------------------------------------------- #
def _set_paragraph_text(paragraph, text: str) -> None:
    """Replace a paragraph's text with `text`, keeping its paragraph style."""
    for run in list(paragraph.runs):
        run._element.getparent().remove(run._element)
    paragraph.add_run(text)


def anonymize_docx(
    in_path: str | Path,
    out_path: str | Path,
    doc: ExtractedDoc,
    anon: Anonymization,
) -> None:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    src_text = _source_to_text(doc, anon)
    document = Document(str(in_path))

    para_idx = 0
    table_idx = 0
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            key = f"para{para_idx}"
            if key in src_text:
                _set_paragraph_text(Paragraph(child, document), src_text[key])
            para_idx += 1
        elif child.tag == qn("w:tbl"):
            table = Table(child, document)
            for r, row in enumerate(table.rows):
                for c, cell in enumerate(row.cells):
                    key = f"table{table_idx}:r{r}c{c}"
                    if key in src_text:
                        # Write into the first paragraph, drop the rest.
                        first = cell.paragraphs[0]
                        _set_paragraph_text(first, src_text[key].replace("\n", " "))
                        for extra in cell.paragraphs[1:]:
                            extra._element.getparent().remove(extra._element)
            table_idx += 1

    document.save(str(out_path))


# --------------------------------------------------------------------------- #
# Excel
# --------------------------------------------------------------------------- #
def anonymize_xlsx(
    in_path: str | Path,
    out_path: str | Path,
    doc: ExtractedDoc,
    anon: Anonymization,
) -> None:
    from openpyxl import load_workbook

    src_text = _source_to_text(doc, anon)
    wb = load_workbook(str(in_path))  # not read-only: we need to write
    for source, text in src_text.items():
        if "!" not in source:
            continue
        sheet_name, coord = source.split("!", 1)
        if sheet_name in wb.sheetnames:
            wb[sheet_name][coord] = text
    wb.save(str(out_path))
    wb.close()


SUPPORTED = {".docx": anonymize_docx, ".xlsx": anonymize_xlsx}


def anonymize_file(
    in_path: str | Path,
    out_path: str | Path,
    doc: ExtractedDoc,
    anon: Anonymization,
) -> None:
    """Write an anonymized .docx or .xlsx (dispatch by extension)."""
    ext = Path(in_path).suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(f"anonymize_file supports {sorted(SUPPORTED)}, got {ext!r}")
    SUPPORTED[ext](in_path, out_path, doc, anon)
