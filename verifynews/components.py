"""Claim evidence UI components."""
import html
import re
from urllib.parse import urlparse

import streamlit as st

from .verification import (
    WIKIPEDIA_LANGUAGES,
    load_xfact_index,
    predict_claim_with_evidence,
    search_evidence,
)

def render_prior_factchecks(claim):
    """Find textually similar fact-checked claims without inventing a new verdict."""
    matched_records = []
    try:
        records, vectorizer, claim_matrix = load_xfact_index()
        if records is None:
            st.caption("Multilingual reference dataset is not installed.")
            return matched_records
        query = vectorizer.transform([claim])
        scores = (claim_matrix @ query.T).toarray().ravel()
        best = scores.argsort()[-3:][::-1]
        close = [int(i) for i in best if scores[i] >= 0.58]
        if not close:
            st.caption("No close matching claim in the multilingual fact-check reference set.")
            return matched_records
        st.caption("Similar claims from the X-FACT research dataset. Similar wording does not guarantee this is the same event; check each original source.")
        for i in close[:2]:
            row = records.iloc[i]
            st.markdown(f"**Published rating: {row['label']}** · Text match {scores[i]:.0%}")
            st.write(row["claim"])
            details = [part for part in (row["site"], row["language"], row["reviewDate"]) if part]
            if details:
                st.caption(" · ".join(details))
            if row["evidence_1"]:
                st.write(row["evidence_1"])
            if row["link_1"]:
                st.markdown(f"[Open original fact-check/evidence]({row['link_1']})")
            matched_records.append({
                "provider": f"Prior fact-check · {row['site'] or 'X-FACT'}",
                "source_title": row["site"] or "X-FACT reference record",
                "url": row["link_1"], "excerpt": row["evidence_1"],
                "published_at": row["reviewDate"], "relation": "Unreviewed",
                "related_claim": row["claim"], "reference_rating": row["label"],
                "similarity": float(scores[i]),
            })
        return matched_records
    except Exception as error:
        st.warning(f"Could not search the local multilingual claim reference ({type(error).__name__}).")
        return matched_records

def render_claim_check(claim, claim_vectorizer=None, claim_model=None, evidence_language="en", xlmr=None):
    case_record = {"claim": claim, "evidence": [], "estimates": []}
    st.markdown(f"**Claim:** {claim}")
    st.markdown("**Previously fact-checked claims**")
    case_record["evidence"].extend(render_prior_factchecks(claim))
    st.markdown("**Wikipedia API source search**")
    matches = []
    search_failed = False
    try:
        matches = search_evidence(claim, evidence_language)
    except Exception as error:
        language_name = next((name for name, code in WIKIPEDIA_LANGUAGES.items() if code == evidence_language), "selected")
        st.warning(f"Wikipedia API search failed for the {language_name} edition: {error}. No verdict was inferred.")
        search_failed = True
    if not matches and not search_failed:
        language_name = next((name for name, code in WIKIPEDIA_LANGUAGES.items() if code == evidence_language), "selected")
        st.info(f"Wikipedia API search completed for the {language_name} edition and found no related pages. This does not mean the claim is false.")
    retrieved_evidence, source_domains = [], set()
    if matches:
        language_name = next((name for name, code in WIKIPEDIA_LANGUAGES.items() if code == evidence_language), "selected")
        st.success(f"Wikipedia API search completed · {len(matches)} related pages found · {language_name}")
        st.caption("Wikipedia supplies fuller page extracts and revision dates. These are context to inspect, not independent sources or proof.")
        search_terms = list(dict.fromkeys(match.get("matched_query", "") for match in matches if match.get("matched_query")))
        if search_terms:
            st.caption("Search phrase(s): " + " · ".join(f"“{term}”" for term in search_terms))
        for match in matches[:3]:
            title = html.unescape(re.sub(r"<[^>]+>", "", match.get("title", "Wikipedia article")))
            excerpt = html.unescape(re.sub(r"<[^>]+>", "", match.get("extract", "")))
            if excerpt:
                retrieved_evidence.append(excerpt)
            case_record["evidence"].append({
                "provider": "Wikipedia context",
                "source_title": title,
                "url": match.get("fullurl", ""),
                "excerpt": excerpt,
                "published_at": match.get("revision_date", ""),
                "relation": "Unreviewed",
            })
            if match.get("fullurl"):
                domain = urlparse(match["fullurl"]).netloc.lower()
                if domain:
                    source_domains.add(domain)
            with st.expander(title, expanded=(len(retrieved_evidence) == 1)):
                if match.get("revision_date"):
                    st.caption(f"Wikipedia page revision · {match['revision_date']}")
                if excerpt:
                    st.write(excerpt)
                else:
                    st.caption("No readable extract was returned for this page.")
                if match.get("fullurl"):
                    st.markdown(f"[Open the Wikipedia article]({match['fullurl']})")
    if len(source_domains) < 2:
        st.info(f"**Evidence status: Not enough independent sources.** Retrieved pages cover {len(source_domains)} source domain(s); Wikipedia alone cannot establish a verdict.")

    st.markdown("**Claim-and-evidence model outputs**")
    if retrieved_evidence:
        estimates = predict_claim_with_evidence(claim, " ".join(retrieved_evidence), claim_vectorizer, claim_model, xlmr)
        if estimates:
            for label, model_name in estimates:
                st.warning(f"Research estimate · {model_name}: **{label}**")
                case_record["estimates"].append({"model": model_name, "label": label})
            st.caption("These are model estimates from retrieved context, not truth verdicts. Review the linked source pages; the app abstains when it lacks independent corroboration.")
        else:
            st.info("No trained claim-and-evidence model is available. Install the prepared verification data or fine-tuned XLM-R checkpoint.")
    else:
        st.info("No model estimate for this claim: the app did not retrieve readable evidence to pair with the claim.")
    return case_record
