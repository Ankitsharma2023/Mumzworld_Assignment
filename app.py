"""
Streamlit demo for the PDP auditor.

Run:
    streamlit run app.py

This is what the 3-minute Loom records. The UI is deliberately minimal
because the demo is about the *output*, not the framing.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from src.auditor import Auditor
from src.schema import PDPInput, AuditResult, Severity

from dotenv import load_dotenv
import os

load_dotenv()

print("KEY:", os.getenv("OPENROUTER_API_KEY"))


PDP_DIR = Path(__file__).parent / "data" / "pdps"
SEV_COLORS = {
    Severity.LOW: "#888888",
    Severity.MEDIUM: "#d97706",
    Severity.HIGH: "#dc2626",
}


st.set_page_config(page_title="Mumzworld PDP Auditor", layout="wide")
st.title("Mumzworld PDP Quality Auditor")
st.caption(
    "Audits 3P marketplace listings for completeness, claim grounding, "
    "bilingual quality, and safety. Returns a structured, citable report."
)

# ----- input -----
fixtures = sorted([p.name for p in PDP_DIR.glob("*.json")])
col_in, col_out = st.columns([1, 2])

with col_in:
    st.subheader("Input")
    choice = st.selectbox("Pick a fixture", fixtures, index=0)
    fixture_path = PDP_DIR / choice
    raw_text = fixture_path.read_text(encoding="utf-8")
    edited = st.text_area("PDP JSON (editable)", raw_text, height=420)
    run_btn = st.button("Audit", type="primary", use_container_width=True)

# ----- run -----
if run_btn:
    try:
        pdp = PDPInput.model_validate(json.loads(edited))
    except Exception as e:
        st.error(f"Input failed validation: {e}")
        st.stop()

    with st.spinner("Auditing…"):
        auditor = Auditor()
        result = auditor.audit(pdp)

    st.session_state["last_result"] = result

# ----- output -----
result: AuditResult | None = st.session_state.get("last_result")

with col_out:
    st.subheader("Audit result")
    if result is None:
        st.info("Run an audit on the left to see the output here.")
    elif not result.auditable:
        st.warning(f"**Refused.** {result.refusal_reason}")
        st.caption(f"Model: `{result.model_used}`")
    else:
        c1, c2 = st.columns([1, 3])
        c1.metric("Quality score", result.quality_score)
        c2.write(result.score_rationale)

        if result.issues:
            st.markdown("### Issues")
            for issue in result.issues:
                color = SEV_COLORS[issue.severity]
                st.markdown(
                    f"<div style='border-left: 4px solid {color}; padding: 6px 12px; margin-bottom: 8px;'>"
                    f"<b>{issue.type.value}</b> "
                    f"<span style='color:{color}'>[{issue.severity.value}]</span> "
                    f"&nbsp;<i>conf {issue.confidence:.2f}</i><br>"
                    f"<small>field: <code>{issue.field}</code></small><br>"
                    f"{issue.evidence}"
                    "</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.success("No issues flagged.")

        if result.suggested_fixes:
            st.markdown("### Suggested fixes")
            for fix in result.suggested_fixes:
                with st.expander(f"`{fix.field}` (conf {fix.confidence:.2f})"):
                    st.markdown(f"**Current:** {fix.current or '_(empty)_'}")
                    st.markdown(f"**Suggested:** {fix.suggested}")
                    st.caption(f"Why: {fix.reasoning}")

        if result.generated_ar_title or result.generated_ar_description:
            st.markdown("### Native Arabic copy (generated, not translated)")
            if result.generated_ar_title:
                st.markdown(
                    f"<div dir='rtl' style='font-size:1.1em'><b>{result.generated_ar_title}</b></div>",
                    unsafe_allow_html=True,
                )
            if result.generated_ar_description:
                st.markdown(
                    f"<div dir='rtl'>{result.generated_ar_description}</div>",
                    unsafe_allow_html=True,
                )

        with st.expander("Raw JSON output"):
            st.json(result.model_dump(mode="json"))

        st.caption(f"Model: `{result.model_used}`")
