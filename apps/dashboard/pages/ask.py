"""Ask / QA page — grounded question answering with citations and abstention."""
from __future__ import annotations

import streamlit as st

from geomemory import GeoMemory


def render(ws: GeoMemory) -> None:
    st.header("💬 Ask / QA")

    model_path = ws.settings.model_path
    if not model_path:
        st.warning(
            "No LLM backend configured (`model_path`). Answers will **abstain** "
            "until a GGUF model path is set in **Settings**."
        )

    with st.form("ask_form"):
        question = st.text_area("Question", placeholder="e.g. What vegetation indices detect crop stress?")
        collections = [c.name for c in ws.list_collections()]
        sel = st.multiselect("Scope (collections)", collections)
        col_ids = {c.name: c.id for c in ws.list_collections()}
        submitted = st.form_submit_button("Ask", type="primary")

    if submitted:
        if not question.strip():
            st.warning("Enter a question.")
            return
        with st.spinner("Retrieving and answering…"):
            try:
                ans = ws.ask(question, collections=[col_ids[c] for c in sel] or None)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Ask failed: {exc}")
                return
        st.session_state["gm_last_answer"] = ans

    ans = st.session_state.get("gm_last_answer")
    if ans is None:
        return

    if ans.abstained:
        st.markdown("### 🤷 Abstained")
        st.info(f"**Reason:** {ans.abstention_reason or 'no reason given'}")
        if ans.text:
            st.caption(ans.text)
    else:
        st.markdown("### Answer")
        st.write(ans.text)

    if ans.sources:
        with st.expander(f"Sources ({len(ans.sources)})"):
            for i, hit in enumerate(ans.sources, start=1):
                locator = (hit.locator or {}).get("file", "") if hit.locator else ""
                st.markdown(
                    f"**[{i}]** score={hit.score:.3f} · `{hit.id}`"
                    + (f" · `{locator}`" if locator else "")
                )
                snippet = (hit.text or "")[:300]
                st.caption(snippet + ("…" if len(hit.text or "") > 300 else ""))

    if ans.citations:
        with st.expander(f"Citations ({len(ans.citations)})"):
            for cit in ans.citations:
                st.markdown(f"- `{cit.segment_id}` · locator={cit.locator}")

    if not ans.abstained:
        with st.form("ask_feedback"):
            rating = st.slider("Answer rating", 1, 5, 3)
            fb_submitted = st.form_submit_button("Submit feedback")
        if fb_submitted:
            from geomemory.core.models import FeedbackEvent

            try:
                ws.record_feedback(
                    FeedbackEvent(
                        target_type="answer",
                        target_id=ans.retrieval_run_id or "answer",
                        label="answer_rating",
                        payload={"rating": int(rating), "question": ans.model},
                    )
                )
                st.success("Feedback recorded.")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Feedback failed: {exc}")
