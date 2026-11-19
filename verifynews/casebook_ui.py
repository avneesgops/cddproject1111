"""Case creation, review workflow, and evidence map UI."""
import html
import re
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from .config import CASE_STATUSES
from .components import render_claim_check
from .storage import (
    build_case_brief,
    get_verification_case,
    list_verification_cases,
    save_verification_case,
    update_evidence_relation,
    update_verification_case,
)
from .verification import extract_claims

def clear_article_url():
    """Reset the URL field before the next link is entered."""
    st.session_state["article_url_input"] = ""
    st.session_state.pop("analysis_payload", None)

def clear_last_analysis():
    """Discard a rendered result when the user changes its source text or URL."""
    st.session_state.pop("analysis_payload", None)

def save_case_from_form(analysis):
    """Persist an analysis and reset its input fields before Streamlit reruns."""
    case_title = st.session_state.get("case_title_input", "").strip() or "Untitled review case"
    save_verification_case({**analysis, "title": case_title})
    st.session_state.pop("casebook_selected_id", None)
    st.session_state["casebook_status_filter"] = "New"
    st.session_state["case_title_input"] = analysis.get("title", "Pasted article review")
    st.session_state["article_url_input"] = ""
    st.session_state["pasted_article_text"] = ""
    st.session_state.pop("analysis_payload", None)
    st.session_state["case_created_flash"] = "Analysis saved to your casebook."

def show_result(text, source, title="", domain="", published=None, evidence_language="en", article_url=""):
    st.subheader("Claim-by-claim evidence check")
    caption = f"Input: {source} · {title or 'Untitled article'} · {domain or 'Pasted text'}"
    if published:
        caption += f" · Published: {published.date()}"
    st.caption(caption)
    st.caption("Candidate claims are matched to prior fact-checks and searched against Wikipedia. Retrieved pages are context, not proof of a verdict.")
    claims = extract_claims(text)
    case_claims = []
    if not claims:
        st.info("No clear sentence-length claims could be extracted. Try pasting more article text.")
    else:
        st.caption(f"Reviewing up to {len(claims)} candidate claims")
        for index, claim in enumerate(claims, start=1):
            with st.expander(f"Claim {index}: {claim[:100]}{'…' if len(claim) > 100 else ''}", expanded=(index == 1)):
                case_claims.append(render_claim_check(
                    claim, st.session_state.get("claim_vectorizer"), st.session_state.get("claim_model"),
                    evidence_language, st.session_state.get("xlmr_verifier"),
                ))

    case_analysis = {
        "title": title or (domain if source == "URL" else "Pasted article review"),
        "input_type": source,
        "publisher": domain,
        "article_url": article_url,
        "published_at": published.isoformat() if hasattr(published, "isoformat") else str(published or ""),
        "article_text": text,
        "claims": case_claims,
    }
    with st.form("save_verification_case_form", clear_on_submit=False):
        st.text_input("Save this analysis as a review case", value=case_analysis["title"], key="case_title_input")
        st.caption("The case stores candidate claims, retrieved references, article details, and the model estimates shown above. Source relationships begin as Unreviewed for human assessment.")
        st.form_submit_button(
            "Save to casebook", type="primary",
            on_click=save_case_from_form, args=(case_analysis,),
        )

def _format_case_time(value):
    if not value:
        return "Not recorded"
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    return timestamp.strftime("%d %b %Y · %H:%M UTC") if not pd.isna(timestamp) else str(value)

def _save_case_status_from_widget(case_id, widget_key):
    case = get_verification_case(case_id)
    if not case:
        return
    status = st.session_state.get(widget_key, case["status"])
    update_verification_case(case_id, status, case["reviewer_notes"])
    st.session_state["casebook_flash"] = f"Case moved to {status}."
    st.session_state["casebook_status_filter"] = status
    if status == "Closed" and st.session_state.get("casebook_selected_id") == case_id:
        st.session_state.pop("casebook_selected_id", None)


def _save_evidence_relation_from_widget(evidence_id, widget_key):
    relation = st.session_state.get(widget_key, "Unreviewed")
    update_evidence_relation(evidence_id, relation)
    st.session_state["casebook_flash"] = "Evidence label saved."


def _reopen_case(case_id):
    case = get_verification_case(case_id)
    if not case:
        return
    update_verification_case(case_id, "Assigned for review", case["reviewer_notes"])
    st.session_state["casebook_status_filter"] = "Assigned for review"
    st.session_state["casebook_flash"] = "Case reopened and assigned for review."


def render_casebook():
    st.subheader("Verification casebook")
    st.caption("Move cases between saved workflow boxes. Open an active case to review its claims, evidence, and notes. Closed cases stay in the record but cannot be opened.")
    cases = list_verification_cases()
    if not cases:
        st.info("No cases saved yet. Analyze an article and choose **Save to casebook** to start a case.")
        return

    status_counts = {status: sum(case["status"] == status for case in cases) for status in CASE_STATUSES}
    overview_columns = st.columns(5)
    overview_columns[0].metric("New", status_counts["New"])
    overview_columns[1].metric("Assigned for review", status_counts["Assigned for review"])
    overview_columns[2].metric("Evidence found", status_counts["Evidence found"])
    overview_columns[3].metric("Needs follow-up", status_counts["Needs follow-up"])
    overview_columns[4].metric("Closed", status_counts["Closed"])

    selected_id = st.session_state.get("casebook_selected_id")
    case_ids = {case["id"] for case in cases}
    if selected_id not in case_ids:
        st.session_state.pop("casebook_selected_id", None)
        selected_id = None

    selected_case = next((item for item in cases if item["id"] == selected_id), None)
    if selected_id and selected_case and selected_case["status"] != "Closed":
        case = get_verification_case(selected_id)
        if not case:
            st.session_state.pop("casebook_selected_id", None)
            st.warning("This case could not be loaded. Return to the case list and try again.")
            return

        if st.button("← All cases", key="back_to_case_list"):
            st.session_state.pop("casebook_selected_id", None)
            st.rerun()
        st.title(case["title"])
        metadata = [case["input_type"], case["publisher"] or "Publisher not supplied", f"Created {_format_case_time(case['created_at'])}"]
        st.caption(" · ".join(metadata))
        if case["article_url"]:
            st.markdown(f"[Open original article]({case['article_url']})")

        if flash := st.session_state.pop("casebook_flash", None):
            st.success(flash)

        assignment_column, claims_column, sources_column = st.columns([2, 1, 1])
        with assignment_column:
            st.selectbox(
                "Assign this case to a workflow box",
                CASE_STATUSES,
                index=CASE_STATUSES.index(case["status"]) if case["status"] in CASE_STATUSES else 0,
                key=f"case_status_detail_{selected_id}",
                on_change=_save_case_status_from_widget,
                args=(selected_id, f"case_status_detail_{selected_id}"),
                help="This status saves immediately and moves the case into the matching box.",
            )
        evidence_items = [evidence for claim in case["claims"] for evidence in claim["evidence"]]
        source_domains = {
            urlparse(item["url"]).netloc.lower()
            for item in evidence_items if item["url"] and urlparse(item["url"]).netloc
        }
        claims_column.metric("Candidate claims", len(case["claims"]))
        sources_column.metric("Source domains", len(source_domains))

        notes_key = f"case_notes_{selected_id}"
        with st.form(f"case_notes_form_{selected_id}"):
            reviewer_notes = st.text_area(
                "Reviewer notes", value=case["reviewer_notes"], height=100,
                key=notes_key,
                placeholder="What evidence is missing? What should be checked next?",
            )
            save_notes = st.form_submit_button("Save reviewer notes")
        if save_notes:
            latest_case = get_verification_case(selected_id)
            update_verification_case(selected_id, latest_case["status"], reviewer_notes)
            st.session_state["casebook_flash"] = "Reviewer notes saved."
            st.rerun()

        st.markdown("#### Claim evidence map")
        st.caption("Evidence labels describe how a source relates to this claim; they do not change the case workflow status or create a model verdict.")
        relation_options = ["Unreviewed", "Context", "Supports claim", "Contradicts claim", "Unclear / needs review"]
        if not case["claims"]:
            st.info("This case has no extracted claims. Re-analyze the article to add candidate claims.")
        for claim in case["claims"]:
            with st.expander(f"Claim {claim['claim_index']}: {claim['claim_text'][:105]}{'…' if len(claim['claim_text']) > 105 else ''}"):
                st.write(claim["claim_text"])
                if claim["estimates"]:
                    st.caption("Research estimates · not verdicts")
                    for estimate in claim["estimates"]:
                        st.write(f"{estimate['model']}: **{estimate['label']}**")
                if not claim["evidence"]:
                    st.info("No source records were retrieved for this claim.")
                for evidence in claim["evidence"]:
                    with st.container(border=True):
                        source_name = evidence["source_title"] or evidence["provider"]
                        st.markdown(f"**{html.escape(source_name)}** · {html.escape(evidence['provider'])}")
                        if evidence["published_at"]:
                            st.caption(f"Published or revised: {html.escape(evidence['published_at'])}")
                        if evidence["related_claim"]:
                            st.caption(f"Similar prior claim: {evidence['related_claim']}")
                        if evidence["reference_rating"]:
                            st.caption(f"Original reference rating: {evidence['reference_rating']} · not applied to this claim")
                        if evidence["excerpt"]:
                            st.write(evidence["excerpt"])
                        if evidence["url"]:
                            st.markdown(f"[Open source record]({evidence['url']})")
                        st.selectbox(
                            "Evidence relationship",
                            relation_options,
                            index=relation_options.index(evidence["relation"]) if evidence["relation"] in relation_options else 0,
                            key=f"evidence_relation_{evidence['id']}",
                            on_change=_save_evidence_relation_from_widget,
                            args=(evidence["id"], f"evidence_relation_{evidence['id']}"),
                            help="Saved as soon as you choose a label.",
                        )

        with st.expander("Activity and investigation brief"):
            st.markdown("#### Case activity")
            if case["activity"]:
                for event in case["activity"]:
                    st.markdown(f"**{_format_case_time(event['occurred_at'])}** · {html.escape(event['event'])}")
            else:
                st.caption("No activity recorded yet.")
            st.markdown("#### Investigation brief")
            filename = re.sub(r"[^a-zA-Z0-9-]+", "-", case["title"]).strip("-").lower() or "verifynews-case"
            st.download_button(
                "Download case brief (.md)", data=build_case_brief(case),
                file_name=f"{filename}-brief.md", mime="text/markdown",
                key=f"download_case_brief_{selected_id}",
            )
        return

    selected_status = st.radio(
        "Show cases in",
        CASE_STATUSES,
        horizontal=True,
        key="casebook_status_filter",
        label_visibility="collapsed",
    )
    bucket_cases = [case for case in cases if case["status"] == selected_status]
    st.markdown(f"#### {selected_status} · {len(bucket_cases)}")
    if not bucket_cases:
        st.info(f"No cases in **{selected_status}**. Select a case above to move it into this box.")
        return

    for case in bucket_cases:
        with st.container(border=True):
            title_column, details_column, status_column, open_column = st.columns([4, 2, 2, 1.5], vertical_alignment="center")
            with title_column:
                st.markdown(f"**{case['title']}**")
                st.caption(f"{case['publisher'] or 'Pasted article'} · {case['claim_count']} claims · Updated {_format_case_time(case['updated_at'])}")
            with details_column:
                st.caption(f"Created {_format_case_time(case['created_at'])}")
            with status_column:
                if case["status"] == "Closed":
                    st.caption("Closed")
                else:
                    st.selectbox(
                        "Move to box",
                        CASE_STATUSES,
                        index=CASE_STATUSES.index(case["status"]) if case["status"] in CASE_STATUSES else 0,
                        key=f"case_status_board_{case['id']}",
                        on_change=_save_case_status_from_widget,
                        args=(case["id"], f"case_status_board_{case['id']}"),
                        label_visibility="collapsed",
                    )
            with open_column:
                if case["status"] == "Closed":
                    st.button(
                        "Reopen case", key=f"reopen_case_{case['id']}",
                        on_click=_reopen_case, args=(case["id"],),
                        use_container_width=True,
                    )
                elif st.button("Open", key=f"open_case_{case['id']}", use_container_width=True):
                    st.session_state["casebook_selected_id"] = case["id"]
                    st.rerun()
