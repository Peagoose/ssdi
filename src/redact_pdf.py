"""In-place PDF redaction with PyMuPDF (fitz).

Follows the redaction traps exactly:
  * Locate each value as a TIGHT CONTIGUOUS RUN of words inside ONE (block, line)
    group — never a page-wide union of look-alike words.
  * Numbers match by the EXACT concatenated digits of the run, so a short number
    can't match inside a longer one.
  * Text matches by exact concatenated (whitespace-insensitive) characters.
  * The placeholder is stamped with a font size fitted to the cleared box so it
    never overflows into a neighbouring cell.

`apply_redactions()` truly removes the underlying text (not just draws a box), so
the original value is gone from the file, verifiable by re-extracting text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_NON_DIGIT = re.compile(r"\D")
_WS = re.compile(r"\s+")


@dataclass
class _Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    block: int
    line: int


def _norm_text(s: str) -> str:
    return _WS.sub("", s).lower()


def _digits(s: str) -> str:
    return _NON_DIGIT.sub("", s)


def _is_numeric(value: str) -> bool:
    core = _WS.sub("", value)
    if not core:
        return False
    digits = sum(c.isdigit() for c in core)
    return digits / len(core) > 0.5


def _target_key(value: str) -> tuple[bool, str]:
    """Return (is_numeric, normalized_key) for matching a run against a value."""
    if _is_numeric(value):
        return True, _digits(value)
    return False, _norm_text(value)


def _find_runs(words: list[_Word], value: str):
    """Yield (start, end) index ranges of contiguous words (already within one
    (block,line) group) whose concatenation EXACTLY equals `value`."""
    numeric, target = _target_key(value)
    if not target:
        return
    n = len(words)
    i = 0
    while i < n:
        acc = ""
        matched = None
        for j in range(i, n):
            piece = _digits(words[j].text) if numeric else _norm_text(words[j].text)
            if not piece:
                break  # a word with no matchable content can't be part of a tight run
            acc += piece
            if len(acc) > len(target):
                break  # contiguous concat only grows; can't equal target anymore
            if acc == target:
                matched = j
                break
        if matched is not None:
            yield (i, matched + 1)
            i = matched + 1
        else:
            i += 1


def _group_by_line(words: list[_Word]) -> dict[tuple[int, int], list[_Word]]:
    groups: dict[tuple[int, int], list[_Word]] = {}
    for w in words:
        groups.setdefault((w.block, w.line), []).append(w)
    return groups


def _fit_fontsize(fitz, text: str, rect, max_size: float) -> float:
    """Largest helv font size that fits `text` inside `rect` (width & height)."""
    size = max(4.0, min(max_size, rect.height * 0.8))
    while size > 4.0:
        width = fitz.get_text_length(text, fontname="helv", fontsize=size)
        if width <= rect.width - 2 and size <= rect.height:
            break
        size -= 0.5
    return size


def redact_values(
    in_path: str | Path,
    out_path: str | Path,
    replacements: list[tuple[str, str]],
    fill=(1, 1, 1),
    text_color=(0, 0, 0),
) -> int:
    """Redact each (value -> placeholder) in `replacements` across the PDF.

    Returns the number of redaction boxes applied. Each value is located as a
    tight contiguous word run within a single (block, line); its box is cleared
    and the placeholder stamped in, font-fitted to the box.
    """
    import fitz  # PyMuPDF

    in_path, out_path = Path(in_path), Path(out_path)
    doc = fitz.open(str(in_path))
    total = 0
    try:
        for page in doc:
            raw_words = page.get_text("words")  # (x0,y0,x1,y1,word,block,line,word_no)
            words = [_Word(w[0], w[1], w[2], w[3], w[4], w[5], w[6]) for w in raw_words]
            groups = _group_by_line(words)

            stamps: list[tuple["fitz.Rect", str]] = []
            for value, placeholder in replacements:
                for line_words in groups.values():
                    for start, end in _find_runs(line_words, value):
                        run = line_words[start:end]
                        rect = fitz.Rect(run[0].x0, run[0].y0, run[-1].x1, run[-1].y1)
                        page.add_redact_annot(rect, fill=fill)
                        stamps.append((rect, placeholder))
                        total += 1

            if not stamps:
                continue

            # Remove the underlying text/graphics inside every annot box.
            page.apply_redactions()

            # Stamp placeholders on the cleared boxes, fitted to each box.
            for rect, placeholder in stamps:
                size = _fit_fontsize(fitz, placeholder, rect, max_size=11.0)
                rc = page.insert_textbox(
                    rect, placeholder, fontname="helv", fontsize=size,
                    color=text_color, align=0,
                )
                while rc < 0 and size > 4.0:
                    size -= 1.0
                    rc = page.insert_textbox(
                        rect, placeholder, fontname="helv", fontsize=size,
                        color=text_color, align=0,
                    )
                if rc < 0:
                    # Fallback: baseline point insert so the placeholder always lands.
                    page.insert_text(
                        (rect.x0, rect.y1 - 1), placeholder,
                        fontname="helv", fontsize=min(size, 8.0), color=text_color,
                    )
        doc.save(str(out_path), garbage=4, deflate=True)
    finally:
        doc.close()
    return total
