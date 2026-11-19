"""Claim extraction, evidence retrieval, and research model services."""
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import joblib
import numpy as np
import pandas as pd
import streamlit as st
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, f1_score
from sklearn.svm import LinearSVC

from .config import BASE_DIR, CACHE_DIR

def _artifact_cache_path(name, source_paths):
    """Use a local cache that refreshes whenever one of its source files changes."""
    parts = []
    for path in source_paths:
        stat = path.stat()
        parts.append(f"{path.as_posix()}:{stat.st_size}:{stat.st_mtime_ns}")
    signature = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"{name}-{signature}.joblib"

def _load_cached_artifact(path):
    if not path.exists():
        return None
    try:
        return joblib.load(path)
    except Exception:
        path.unlink(missing_ok=True)
        return None

def _save_cached_artifact(path, value):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.stem}-{os.getpid()}.tmp")
    joblib.dump(value, temporary, compress=1)
    temporary.replace(path)

def _claim_evidence_inputs(frame):
    claims = frame["claim"].astype(str)
    if "evidence" in frame:
        evidence = frame["evidence"].astype(str)
    else:
        evidence_columns = [f"evidence_{i}" for i in range(1, 6) if f"evidence_{i}" in frame]
        if evidence_columns:
            evidence = frame[evidence_columns].astype(str).agg(" ".join, axis=1)
        else:
            evidence = pd.Series([""] * len(frame), index=frame.index)
    return ("Claim: " + claims + " Evidence: " + evidence).tolist()

@st.cache_resource(show_spinner="Loading or preparing the claim-and-evidence model…")
def load_claim_model():
    """Train a four-way claim/evidence baseline and evaluate on untouched splits."""
    folder = BASE_DIR / "datasets" / "verification"
    paths = {
        "train": folder / "train.csv",
        "validation": folder / "validation.csv",
        "in_domain": folder / "in_domain_test.csv",
        "out_of_domain": folder / "out_of_domain_test.csv",
        "zero_shot": folder / "zero_shot_test.csv",
        "averitec_dev": folder / "averitec_dev_holdout.csv",
    }
    if not all(path.exists() for path in paths.values()):
        return None, None, None
    cache_path = _artifact_cache_path("claim-evidence-model", list(paths.values()))
    cached = _load_cached_artifact(cache_path)
    if cached is not None:
        return cached
    train = pd.read_csv(paths["train"], dtype=str).fillna("")
    train = train[train["claim"].str.strip().ne("") & train["label"].str.strip().ne("")]
    vectorizer = TfidfVectorizer(
        token_pattern=r"(?u)\b\w+\b", ngram_range=(1, 2), min_df=2,
        max_features=80000, sublinear_tf=True, dtype=np.float32,
    )
    train_vectors = vectorizer.fit_transform(_claim_evidence_inputs(train))
    y_train = train["label"].astype(str)
    model = LinearSVC(class_weight="balanced", random_state=42)
    model.fit(train_vectors, y_train)
    evaluation = {
        "train_rows": len(train), "train_languages": train["language"].nunique(),
        "train_sources": train["source_dataset"].value_counts().to_dict(), "splits": {},
    }
    for name, path in list(paths.items())[1:]:
        frame = pd.read_csv(path, dtype=str).fillna("")
        frame = frame[frame["claim"].str.strip().ne("") & frame["label"].str.strip().ne("")]
        actual = frame["label"].astype(str)
        predicted = model.predict(vectorizer.transform(_claim_evidence_inputs(frame)))
        evaluation["splits"][name] = {
            "accuracy": accuracy_score(actual, predicted),
            "macro_f1": f1_score(actual, predicted, average="macro", zero_division=0),
            "rows": len(frame), "languages": frame["language"].nunique(),
        }
    result = (vectorizer, model, evaluation)
    _save_cached_artifact(cache_path, result)
    return result

@st.cache_resource(show_spinner=False)
def load_xlmr_verifier():
    """Load an optional fine-tuned XLM-R checkpoint without network access."""
    checkpoint = BASE_DIR / "models" / "xlmr_claim_verifier"
    if not (checkpoint / "config.json").exists():
        return None
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(checkpoint, local_files_only=True)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device).eval()
        return tokenizer, model, device, torch
    except Exception:
        return None

def predict_claim_with_evidence(claim, evidence, vectorizer, model, xlmr=None):
    """Return estimates from every installed claim/evidence model."""
    if not evidence:
        return []
    estimates = []
    if vectorizer is not None and model is not None:
        predicted = model.predict(vectorizer.transform([f"Claim: {claim} Evidence: {evidence}"]))[0]
        estimates.append((str(predicted), "LinearSVC baseline"))
    if xlmr is not None:
        tokenizer, xmodel, device, torch = xlmr
        inputs = tokenizer(claim, evidence, truncation="only_second", max_length=384, return_tensors="pt")
        inputs = {key: value.to(device) for key, value in inputs.items()}
        with torch.inference_mode():
            logits = xmodel(**inputs).logits
        index = int(logits.argmax(dim=-1).item())
        predicted = xmodel.config.id2label.get(index, xmodel.config.id2label.get(str(index), "UNKNOWN"))
        estimates.append((str(predicted), "Fine-tuned XLM-R"))
    return estimates

def extract_claims(text, limit=5):
    """Select complete factual sentences without merging headlines or photo credits."""
    candidates = []
    for paragraph in re.split(r"\n+", text or ""):
        paragraph = " ".join(paragraph.split())
        if paragraph:
            candidates.extend(re.split(r"(?<=[.!?؟।。！？])\s+", paragraph))
    claims, seen = [], set()
    for sentence in candidates:
        sentence = sentence.strip(" \t\r\n\"'“”")
        # Headline fragments and image-credit lines often lack sentence endings.
        if not re.search(r"[.!?؟।。！？][\"'”’)]?$", sentence):
            continue
        # Rhetorical/interview questions are not factual propositions to check.
        if "?" in sentence or "؟" in sentence:
            continue
        words = sentence.split()
        if len(words) < 8 or len(sentence) < 45:
            continue
        key = re.sub(r"\W+", " ", sentence.lower()).strip()
        if key and key not in seen:
            claims.append(sentence)
            seen.add(key)
        if len(claims) >= limit:
            break
    return claims

WIKIPEDIA_LANGUAGES = {
    "English": "en", "Arabic": "ar", "German": "de", "Spanish": "es",
    "Hindi": "hi", "Indonesian": "id", "Italian": "it", "Georgian": "ka",
    "Polish": "pl", "Portuguese": "pt", "Romanian": "ro", "Serbian": "sr",
    "Tamil": "ta", "Turkish": "tr",
}

@st.cache_data(ttl=3600, show_spinner=False)
def search_evidence(claim, language="en"):
    """Search topic phrases before a long sentence, then return dated page extracts."""
    if language not in WIKIPEDIA_LANGUAGES.values():
        language = "en"
    results = []
    seen_pages = set()
    # Long news sentences commonly contain many details that are absent from
    # Wikipedia titles. Search the named event first (e.g. "Cyclone Akvan").
    topic_pattern = re.compile(
        r"\b(?P<kind>(?i:(?:(?:tropical|severe|super)\s+)?(?:cyclone|cyclonic storm|hurricane|typhoon|earthquake|volcano|flood|wildfire|outbreak|pandemic)))\s+[\"'“‘]?(?P<name>[A-Z][\w’'-]+)"
    )
    concept_pattern = re.compile(
        r"\b([A-Z\w’'-]+(?:\s+[A-Z\w’'-]+){0,2}\s+(?:culture|period|era|transition|revolution|age|civilization|civilisation))\b"
    )

    def compact_query(text, max_chars=240):
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= max_chars:
            return text
        stopwords = {
            "a", "about", "after", "also", "an", "and", "are", "as", "at", "be", "been", "before",
            "between", "by", "for", "from", "had", "has", "have", "he", "her", "his", "how", "in",
            "into", "is", "it", "its", "likely", "may", "of", "on", "or", "over", "said", "she",
            "that", "the", "their", "them", "there", "this", "to", "was", "were", "which", "while",
            "who", "will", "with", "would",
        }
        words = re.findall(r"[\w’'-]+", text, flags=re.UNICODE)
        useful_words = [word for word in words if word.casefold() not in stopwords]
        compact = " ".join(useful_words[:32]) or text
        if len(compact) > max_chars:
            compact = compact[:max_chars].rsplit(" ", 1)[0]
        return compact

    topic_match = topic_pattern.search(claim)
    queries = []
    if topic_match:
        topic = f"{topic_match.group('kind')} {topic_match.group('name')}"
        queries.append(topic)
    # Search concise historical/scientific concepts before the full claim.
    queries.extend(match.group(1) for match in concept_pattern.finditer(claim))
    if re.search(r"hunter[\s-]*gather", claim, re.IGNORECASE) and re.search(r"farm", claim, re.IGNORECASE):
        queries.append("Neolithic transition farming")
    queries.append(compact_query(claim))
    queries = list(dict.fromkeys(query for query in queries if query))

    for query in queries:
        params = urlencode({
            "action": "query", "generator": "search", "gsrsearch": query, "gsrlimit": 3,
            "prop": "extracts|info|revisions", "explaintext": 1, "exchars": 3500,
            "inprop": "url", "rvprop": "timestamp",
            "format": "json", "formatversion": 2,
        })
        request = Request(
            f"https://{language}.wikipedia.org/w/api.php?{params}",
            headers={"Accept": "application/json", "User-Agent": "VerifyNewsCollegeProject/1.0 (educational claim research)"},
        )
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("error"):
            api_error = payload["error"]
            raise RuntimeError(f"Wikipedia API error {api_error.get('code', 'unknown')}: {api_error.get('info', 'request failed')}")
        pages = payload.get("query", {}).get("pages", [])
        pages.sort(key=lambda page: page.get("index", 10_000))
        for page in pages:
            page_key = page.get("pageid") or page.get("title", "").casefold()
            if page_key in seen_pages:
                continue
            seen_pages.add(page_key)
            revisions = page.get("revisions", [])
            results.append({
                "title": page.get("title", "Wikipedia article"),
                "extract": page.get("extract", ""),
                "fullurl": page.get("fullurl", ""),
                "revision_date": revisions[0].get("timestamp", "") if revisions else "",
                "matched_query": query,
            })
            if len(results) >= 3:
                break
        if len(results) >= 3:
            break
    return results

@st.cache_resource(show_spinner="Loading the multilingual fact-check reference…")
def load_xfact_index():
    """Build a local, multilingual index of published fact-check claims."""
    path = BASE_DIR / "datasets" / "xfact_claims.csv"
    if not path.exists():
        return None, None, None
    cache_path = _artifact_cache_path("xfact-search-index", [path])
    cached = _load_cached_artifact(cache_path)
    if cached is not None:
        return cached
    records = pd.read_csv(path, dtype=str).fillna("")
    records = records[records["claim"].str.strip().ne("")].reset_index(drop=True)
    vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b", ngram_range=(1, 2), min_df=2, max_features=80000, sublinear_tf=True, dtype=np.float32)
    claim_matrix = vectorizer.fit_transform(records["claim"])
    result = (records, vectorizer, claim_matrix)
    _save_cached_artifact(cache_path, result)
    return result
