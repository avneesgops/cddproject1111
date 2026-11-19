"""Normalize X-FACT and AVeriTeC into claim/evidence/four-way rating rows."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "datasets"
LABELS = ("SUPPORTED", "REFUTED", "MIXED", "NOT_ENOUGH_EVIDENCE")

XFACT_LABELS = {
    "true": "SUPPORTED",
    "mostly true": "SUPPORTED",
    "false": "REFUTED",
    "mostly false": "REFUTED",
    "half true": "MIXED",
    "partly true/misleading": "MIXED",
    "complicated/hard to categorise": "NOT_ENOUGH_EVIDENCE",
    "other": "NOT_ENOUGH_EVIDENCE",
}
AVERITEC_LABELS = {
    "supported": "SUPPORTED",
    "refuted": "REFUTED",
    "conflicting evidence/cherrypicking": "MIXED",
    "not enough evidence": "NOT_ENOUGH_EVIDENCE",
}


def xfact_rows(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str).fillna("")
    rows = []
    for row in frame.to_dict("records"):
        label = XFACT_LABELS.get(row.get("label", "").strip().lower())
        claim = row.get("claim", "").strip()
        evidence_parts = [
            str(row.get(f"evidence_{i}", "")).strip()
            for i in range(1, 6)
            if str(row.get(f"evidence_{i}", "")).strip()
        ]
        if not label or not claim or not evidence_parts:
            continue
        rows.append({
            "claim": claim,
            "evidence": "\n".join(f"Evidence {i}: {text}" for i, text in enumerate(evidence_parts, 1)),
            "label": label,
            "language": row.get("language", ""),
            "site": row.get("site", ""),
            "region": "",
            "source_dataset": "X-FACT",
        })
    return pd.DataFrame(rows)


def averitec_rows(path: Path) -> pd.DataFrame:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for item in raw:
        label = AVERITEC_LABELS.get(str(item.get("label", "")).strip().lower())
        claim = str(item.get("claim", "")).strip()
        evidence_parts = []
        for question_item in item.get("questions", []):
            question = str(question_item.get("question", "")).strip()
            for answer_item in question_item.get("answers", []):
                answer = str(answer_item.get("answer", "")).strip()
                explanation = str(answer_item.get("boolean_explanation", "")).strip()
                if answer:
                    evidence_parts.append(f"Question: {question}\nAnswer: {answer}" + (f"\nExplanation: {explanation}" if explanation else ""))
        if not label or not claim or not evidence_parts:
            continue
        rows.append({
            "claim": claim,
            "evidence": "\n\n".join(evidence_parts),
            "label": label,
            "language": "en",
            "site": str(item.get("reporting_source") or ""),
            "region": str(item.get("location_ISO_code") or ""),
            "source_dataset": "AVeriTeC",
        })
    return pd.DataFrame(rows)


def combine(xfact_path: Path, averitec_path: Path) -> pd.DataFrame:
    return pd.concat([xfact_rows(xfact_path), averitec_rows(averitec_path)], ignore_index=True)


def main() -> None:
    output = DATA / "verification"
    output.mkdir(parents=True, exist_ok=True)
    outputs = {
        "train": combine(DATA / "xfact_claims.csv", DATA / "averitec" / "train.json"),
        "validation": combine(DATA / "xfact_dev.csv", DATA / "averitec" / "dev.json"),
        "in_domain_test": xfact_rows(DATA / "xfact_test.csv"),
        "out_of_domain_test": xfact_rows(DATA / "xfact_ood.csv"),
        "zero_shot_test": xfact_rows(DATA / "xfact_zeroshot.csv"),
        "averitec_dev_holdout": averitec_rows(DATA / "averitec" / "dev.json"),
    }
    for name, frame in outputs.items():
        frame = frame[["claim", "evidence", "label", "language", "site", "region", "source_dataset"]]
        path = output / f"{name}.csv"
        frame.to_csv(path, index=False, encoding="utf-8")
        print(f"{path.relative_to(ROOT)}: {len(frame):,} rows; {frame['language'].nunique()} languages; labels={frame['label'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
