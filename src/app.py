"""Streamlit UI for the Legal PII Anonymizer.

Run (Windows, venv active, model installed):
    streamlit run src/app.py

One calm flow: upload -> review highlighted detections -> download the anonymized
file + reversible key. All detection is genuine (Presidio + NER + checksums); the
FRCP 5.2 redaction policy is configurable in the sidebar.
"""
from __future__ import annotations

import html
import os
import re
import sys
import tempfile
from pathlib import Path

import streamlit as st

# Make `src` importable whether launched via `streamlit run src/app.py` or `-m`.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.analyze import DEFAULT_SCORE_THRESHOLD, build_analyzer_engine  # noqa: E402
from src.anonymize import write_key_csv  # noqa: E402
from src.pipeline import process_file, write_anonymized_output  # noqa: E402
from src.policy import RedactionPolicy, full_placeholder_policy  # noqa: E402

# --------------------------------------------------------------------------- #
# Page + styling
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="Legal PII Anonymizer", page_icon="🛡️", layout="wide")

ACCENT = "#2563eb"
ENTITY_COLORS = {
    "PERSON": "#dbeafe", "ORG": "#e9d5ff", "LOCATION": "#dcfce7", "GPE": "#dcfce7",
    "US_SSN": "#fee2e2", "US_ITIN": "#fee2e2", "US_EIN": "#fed7aa",
    "US_BANK_ROUTING": "#fef08a", "US_BANK_NUMBER": "#fef08a",
    "CREDIT_CARD": "#fecaca", "IBAN_CODE": "#fde68a",
    "US_COURT_DOCKET": "#c7d2fe", "US_BAR_NUMBER": "#ddd6fe",
    "US_DOB": "#fbcfe8", "DATE_TIME": "#f5d0fe",
    "EMAIL_ADDRESS": "#bae6fd", "PHONE_NUMBER": "#a7f3d0",
    "US_DRIVER_LICENSE": "#fed7aa", "US_PASSPORT": "#fed7aa",
}
DEFAULT_COLOR = "#e5e7eb"

st.markdown(
    f"""
    <style>
      .stApp {{ background: #fafafa; }}
      .block-container {{ max-width: 1100px; padding-top: 2rem; }}
      h1 {{ font-weight: 700; letter-spacing: -0.02em; }}
      .subtitle {{ color: #6b7280; font-size: 1.02rem; margin-top: -0.6rem; }}
      .disclaimer {{ background:#fff7ed; border:1px solid #fed7aa; color:#9a3412;
        padding:0.6rem 0.9rem; border-radius:10px; font-size:0.86rem; }}
      .doc {{ background:#fff; border:1px solid #e5e7eb; border-radius:12px;
        padding:1.1rem 1.3rem; line-height:1.9; font-size:0.95rem;
        white-space:pre-wrap; word-break:break-word; max-height:60vh; overflow:auto; }}
      mark {{ padding:0.05em 0.28em; border-radius:5px; }}
      .tag {{ font-size:0.62em; color:#374151; opacity:0.7; margin-left:0.25em;
        font-weight:600; text-transform:none; }}
      .chip {{ display:inline-block; background:#fff; border:1px solid #e5e7eb;
        border-radius:999px; padding:0.28rem 0.7rem; margin:0.18rem; font-size:0.85rem; }}
      .chip b {{ color:{ACCENT}; }}
      .ph {{ background:{ACCENT}1a; color:{ACCENT}; padding:0.05em 0.3em;
        border-radius:5px; font-weight:600; }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🛡️ Legal PII Anonymizer")
st.markdown(
    '<p class="subtitle">Detect and redact personal information in English legal '
    "documents — fully local, reversible, court-style.</p>",
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="disclaimer">Assists FRCP&nbsp;5.2 compliance but is <b>not legal '
    "advice</b>. Every output must be verified by a human before filing.</div>",
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- #
# Engine (cached across reruns)
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner="Loading detection engine (first time is slow)…")
def _load_engine():
    return build_analyzer_engine()


# --------------------------------------------------------------------------- #
# Sidebar — redaction policy
# --------------------------------------------------------------------------- #
def _policy_from_sidebar() -> RedactionPolicy | None:
    st.sidebar.header("Redaction policy")
    mode = st.sidebar.radio(
        "Mode",
        ["FRCP 5.2 partial redaction (legal default)", "Full placeholder (maximum)"],
        help="FRCP keeps last-4 of SSNs/accounts, year of DOB, etc. "
        "Full placeholder replaces every value with a reversible token.",
    )
    if mode.startswith("Full"):
        return full_placeholder_policy()

    st.sidebar.caption("Per-rule overrides")
    ssn = "last4" if st.sidebar.checkbox("SSN / ITIN → last 4", True) else "placeholder"
    fin = "last4" if st.sidebar.checkbox("Accounts / cards → last 4", True) else "placeholder"
    dob = "year" if st.sidebar.checkbox("Date of birth → year", True) else "placeholder"
    addr = "redact" if st.sidebar.checkbox("Home addresses → redact", True) else "placeholder"
    return RedactionPolicy(ssn=ssn, financial=fin, dob=dob, address=addr)


def _threshold_from_sidebar() -> float:
    st.sidebar.header("Advanced")
    return st.sidebar.slider(
        "Detection confidence threshold", 0.0, 1.0, float(DEFAULT_SCORE_THRESHOLD), 0.05
    )


# --------------------------------------------------------------------------- #
# Highlight rendering
# --------------------------------------------------------------------------- #
def highlight_original(text: str, entities) -> str:
    """Wrap detected spans with a colored mark + a small type tag."""
    parts, cursor = [], 0
    for e in sorted(entities, key=lambda x: x.start):
        if e.start < cursor:
            continue  # skip any residual overlap
        parts.append(html.escape(text[cursor:e.start]))
        color = ENTITY_COLORS.get(e.entity_type, DEFAULT_COLOR)
        label = e.entity_type.replace("US_", "").replace("_", " ").title()
        parts.append(
            f'<mark style="background:{color}" title="{html.escape(e.entity_type)} '
            f'({e.score:.2f})">{html.escape(text[e.start:e.end])}'
            f'<span class="tag">{html.escape(label)}</span></mark>'
        )
        cursor = e.end
    parts.append(html.escape(text[cursor:]))
    return f'<div class="doc">{"".join(parts)}</div>'


_PLACEHOLDER_RE = re.compile(r"(\[[A-Z]+_\d+\]|XXX-XX-\d{4}|\*{2,}\d{4}|\[ADDRESS_REDACTED\])")


def render_anonymized(text: str) -> str:
    """Show anonymized text, accenting placeholders/masks."""
    escaped = html.escape(text)
    highlighted = _PLACEHOLDER_RE.sub(lambda m: f'<span class="ph">{m.group(0)}</span>', escaped)
    return f'<div class="doc">{highlighted}</div>'


# --------------------------------------------------------------------------- #
# Main flow
# --------------------------------------------------------------------------- #
policy = _policy_from_sidebar()
threshold = _threshold_from_sidebar()

uploaded = st.file_uploader(
    "Upload a legal document", type=["pdf", "docx", "xlsx"],
    help="PDF, Word (.docx), or Excel (.xlsx). Processed locally; nothing leaves your machine.",
)

if uploaded is None:
    st.info("Upload a PDF, Word, or Excel file to begin.")
    st.stop()

# Persist the upload to a temp file so extractors/redactors can open it by path.
suffix = Path(uploaded.name).suffix.lower()
with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
    tmp.write(uploaded.getbuffer())
    in_path = tmp.name

try:
    engine = _load_engine()
except OSError:
    st.error(
        "The English model `en_core_web_lg` isn't installed. In your activated "
        "venv run:\n\n`python -m spacy download en_core_web_lg`"
    )
    st.stop()

with st.spinner("Detecting PII…"):
    processed = process_file(in_path, engine, policy=policy, score_threshold=threshold)

anon = processed.anonymization
counts = anon.counts_by_type()
total = sum(counts.values())

# ---- Downloads up top (no scrolling needed) ----
out_path = str(Path(tempfile.gettempdir()) / f"anonymized_{Path(uploaded.name).stem}{suffix}")
write_anonymized_output(in_path, out_path, processed)
key_path = str(Path(tempfile.gettempdir()) / f"key_{Path(uploaded.name).stem}.csv")
write_key_csv(key_path, anon)

st.subheader(f"Detected {total} PII value{'s' if total != 1 else ''}")
dl1, dl2 = st.columns(2)
with dl1:
    with open(out_path, "rb") as f:
        st.download_button("⬇️ Anonymized file", f.read(),
                           file_name=f"anonymized_{uploaded.name}", use_container_width=True)
with dl2:
    with open(key_path, "rb") as f:
        st.download_button("⬇️ Re-identification key (CSV)", f.read(),
                           file_name=f"key_{Path(uploaded.name).stem}.csv",
                           use_container_width=True)

# ---- Per-type summary ----
if counts:
    chips = "".join(
        f'<span class="chip">{t.replace("US_", "").replace("_", " ").title()} '
        f"<b>{n}</b></span>"
        for t, n in sorted(counts.items(), key=lambda kv: -kv[1])
    )
    st.markdown(chips, unsafe_allow_html=True)

# ---- Views ----
view = st.radio("View", ["Highlighted original", "Anonymized"], horizontal=True)
if view == "Highlighted original":
    st.markdown(highlight_original(processed.doc.text, processed.entities),
                unsafe_allow_html=True)
else:
    if st.toggle("Reveal original values"):
        st.markdown(highlight_original(processed.doc.text, processed.entities),
                    unsafe_allow_html=True)
    else:
        st.markdown(render_anonymized(anon.text), unsafe_allow_html=True)

with st.expander("Re-identification key"):
    st.dataframe(
        [{"Placeholder": r.placeholder, "Type": r.entity_type,
          "Original": r.original, "Count": r.occurrences} for r in anon.key],
        use_container_width=True, hide_index=True,
    )
