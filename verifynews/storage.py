"""Local SQLite persistence and investigation brief formatting."""
import json
import sqlite3
import uuid

import pandas as pd

from .config import CASE_DB_PATH

def _case_connection():
    CASE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(CASE_DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            input_type TEXT NOT NULL,
            publisher TEXT NOT NULL DEFAULT '',
            article_url TEXT NOT NULL DEFAULT '',
            published_at TEXT NOT NULL DEFAULT '',
            article_text TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'New',
            reviewer_notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS case_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            claim_index INTEGER NOT NULL,
            claim_text TEXT NOT NULL,
            estimates_json TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS case_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_claim_id INTEGER NOT NULL REFERENCES case_claims(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            source_title TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL DEFAULT '',
            excerpt TEXT NOT NULL DEFAULT '',
            published_at TEXT NOT NULL DEFAULT '',
            relation TEXT NOT NULL DEFAULT 'Unreviewed',
            related_claim TEXT NOT NULL DEFAULT '',
            reference_rating TEXT NOT NULL DEFAULT '',
            similarity REAL
        );
        CREATE TABLE IF NOT EXISTS case_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            event TEXT NOT NULL,
            occurred_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_case_claims_case ON case_claims(case_id);
        CREATE INDEX IF NOT EXISTS idx_case_evidence_claim ON case_evidence(case_claim_id);
        CREATE INDEX IF NOT EXISTS idx_case_activity_case ON case_activity(case_id, occurred_at);
    """)
    # Keep cases created by the earlier workflow visible in the new review queue.
    connection.execute("UPDATE cases SET status='Assigned for review' WHERE status='Reviewing'")
    connection.commit()
    return connection

def list_verification_cases():
    connection = _case_connection()
    try:
        return [dict(row) for row in connection.execute(
            "SELECT c.id, c.title, c.input_type, c.publisher, c.status, c.created_at, c.updated_at, "
            "(SELECT COUNT(*) FROM case_claims cc WHERE cc.case_id=c.id) AS claim_count "
            "FROM cases c ORDER BY c.updated_at DESC"
        )]
    finally:
        connection.close()

def save_verification_case(analysis):
    case_id = uuid.uuid4().hex
    now = pd.Timestamp.now(tz="UTC").isoformat()
    connection = _case_connection()
    try:
        with connection:
            connection.execute(
                "INSERT INTO cases (id,title,input_type,publisher,article_url,published_at,article_text,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (case_id, analysis["title"], analysis["input_type"], analysis.get("publisher", ""),
                 analysis.get("article_url", ""), analysis.get("published_at", ""), analysis.get("article_text", ""),
                 "New", now, now),
            )
            connection.execute("INSERT INTO case_activity (case_id,event,occurred_at) VALUES (?,?,?)", (case_id, "Case created from an article analysis", now))
            for claim_index, claim in enumerate(analysis.get("claims", []), start=1):
                cursor = connection.execute(
                    "INSERT INTO case_claims (case_id,claim_index,claim_text,estimates_json) VALUES (?,?,?,?)",
                    (case_id, claim_index, claim["claim"], json.dumps(claim.get("estimates", []), ensure_ascii=False)),
                )
                for evidence in claim.get("evidence", []):
                    connection.execute(
                        "INSERT INTO case_evidence (case_claim_id,provider,source_title,url,excerpt,published_at,relation,related_claim,reference_rating,similarity) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (cursor.lastrowid, evidence.get("provider", "Source"), evidence.get("source_title", ""),
                         evidence.get("url", ""), evidence.get("excerpt", ""), evidence.get("published_at", ""),
                         evidence.get("relation", "Unreviewed"), evidence.get("related_claim", ""),
                         evidence.get("reference_rating", ""), evidence.get("similarity")),
                    )
    finally:
        connection.close()
    return case_id

def get_verification_case(case_id):
    connection = _case_connection()
    try:
        case_row = connection.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        if not case_row:
            return None
        result = dict(case_row)
        result["claims"] = []
        claim_rows = connection.execute(
            "SELECT * FROM case_claims WHERE case_id=? ORDER BY claim_index", (case_id,)
        ).fetchall()
        for claim_row in claim_rows:
            claim = dict(claim_row)
            claim["estimates"] = json.loads(claim.pop("estimates_json", "[]"))
            claim["evidence"] = [dict(row) for row in connection.execute(
                "SELECT * FROM case_evidence WHERE case_claim_id=? ORDER BY id", (claim["id"],)
            )]
            result["claims"].append(claim)
        result["activity"] = [dict(row) for row in connection.execute(
            "SELECT event, occurred_at FROM case_activity WHERE case_id=? ORDER BY occurred_at DESC", (case_id,)
        )]
        return result
    finally:
        connection.close()

def update_verification_case(case_id, status, reviewer_notes):
    now = pd.Timestamp.now(tz="UTC").isoformat()
    connection = _case_connection()
    try:
        with connection:
            current = connection.execute("SELECT status,reviewer_notes FROM cases WHERE id=?", (case_id,)).fetchone()
            if not current:
                return
            connection.execute(
                "UPDATE cases SET status=?,reviewer_notes=?,updated_at=? WHERE id=?",
                (status, reviewer_notes, now, case_id),
            )
            if current["status"] != status:
                event = f"Status changed: {current['status']} → {status}"
                connection.execute("INSERT INTO case_activity (case_id,event,occurred_at) VALUES (?,?,?)", (case_id, event, now))
            if current["reviewer_notes"] != reviewer_notes:
                connection.execute("INSERT INTO case_activity (case_id,event,occurred_at) VALUES (?,?,?)", (case_id, "Reviewer notes updated", now))
    finally:
        connection.close()

def update_evidence_relation(evidence_id, relation):
    connection = _case_connection()
    try:
        with connection:
            connection.execute("UPDATE case_evidence SET relation=? WHERE id=?", (relation, evidence_id))
            row = connection.execute(
                "SELECT c.case_id FROM case_evidence e JOIN case_claims c ON c.id=e.case_claim_id WHERE e.id=?",
                (evidence_id,),
            ).fetchone()
            if row:
                now = pd.Timestamp.now(tz="UTC").isoformat()
                connection.execute("UPDATE cases SET updated_at=? WHERE id=?", (now, row["case_id"]))
                connection.execute(
                    "INSERT INTO case_activity (case_id,event,occurred_at) VALUES (?,?,?)",
                    (row["case_id"], f"Evidence relationship labeled: {relation}", now),
                )
    finally:
        connection.close()

def build_case_brief(case):
    lines = [
        f"# Investigation brief: {case['title']}", "",
        f"- **Status:** {case['status']}", f"- **Input:** {case['input_type']}",
        f"- **Publisher:** {case['publisher'] or 'Not supplied'}",
        f"- **Article:** {case['article_url'] or 'Pasted text'}",
        f"- **Created:** {case['created_at']}", f"- **Last updated:** {case['updated_at']}", "",
        "> Research aid: related pages and model outputs are not proof of a claim. Reviewer labels describe this investigation and should be checked against the original sources.", "",
        "## Reviewer notes", "", case["reviewer_notes"] or "No reviewer notes yet.", "",
        "## Claims and evidence", "",
    ]
    if not case["claims"]:
        lines.append("No candidate claims were extracted for this case.")
    for claim in case["claims"]:
        lines.extend([f"### Claim {claim['claim_index']}", "", claim["claim_text"], ""])
        for estimate in claim["estimates"]:
            lines.append(f"- **Model estimate ({estimate.get('model', 'model')}):** {estimate.get('label', 'Unknown')} — not a verified verdict.")
        if not claim["evidence"]:
            lines.extend(["- No source evidence was retrieved for this claim.", ""])
        for evidence in claim["evidence"]:
            label = evidence["relation"]
            lines.append(f"- **{label} · {evidence['provider']} · {evidence['source_title'] or 'Untitled source'}**")
            if evidence["url"]:
                lines.append(f"  - Source: {evidence['url']}")
            if evidence["published_at"]:
                lines.append(f"  - Published or revised: {evidence['published_at']}")
            if evidence["reference_rating"]:
                lines.append(f"  - Original fact-check rating: {evidence['reference_rating']} (similar prior claim; not transferred to this claim)")
            if evidence["related_claim"]:
                lines.append(f"  - Prior checked claim: {evidence['related_claim']}")
            if evidence["excerpt"]:
                lines.append(f"  - Excerpt: {evidence['excerpt']}")
        lines.append("")
    if case["activity"]:
        lines.extend(["## Case activity", ""])
        for event in case["activity"]:
            lines.append(f"- {event['occurred_at']} — {event['event']}")
    return "\n".join(lines).strip() + "\n"
