import json
import sqlite3
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from uuid import uuid4

from app.domain.facts import Conflict, Fact, conflicts
from app.domain.rater import shop
from app.domain.rules import recommend
from app.errors import ClearanceError
from app.services import cases

FACT_NAMES = {
    "insured_name",
    "license_number",
    "license_issued_on",
    "license_expires_on",
    "vin",
    "plate",
    "vehicle_year",
    "prior_policy_expires_on",
    "sdip_points",
    "line_of_business",
}
DATE_FACTS = {"license_issued_on", "license_expires_on", "prior_policy_expires_on"}
INT_FACTS = {"sdip_points", "vehicle_year"}
MANUAL_PROMPT = "manual"
MANUAL_MODEL = "manual"


def checked_facts(
    conn: sqlite3.Connection,
    case_id: str,
    submitted: Sequence[Mapping[str, str]],
) -> list[Fact]:
    cases.require_case(conn, case_id)
    if not submitted:
        raise ClearanceError("The fact set is empty.")
    return [_parse_fact(conn, case_id, item) for item in submitted]


def write_facts(
    conn: sqlite3.Connection,
    case_id: str,
    run_id: str,
    facts: Sequence[Fact],
) -> None:
    conn.execute("DELETE FROM facts WHERE run_id = ?", (run_id,))
    for fact in facts:
        conn.execute(
            """
            INSERT INTO facts (id, case_id, run_id, name, value, document_id, quote)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (uuid4().hex, case_id, run_id, fact.name, fact.value, fact.document_id, fact.quote),
        )


def record_facts(
    conn: sqlite3.Connection,
    case_id: str,
    submitted: Sequence[Mapping[str, str]],
    today: date,
) -> dict:
    parsed = checked_facts(conn, case_id, submitted)
    run_id = _manual_run(conn, case_id)
    write_facts(conn, case_id, run_id, parsed)
    return build_memo(conn, case_id, today)


def build_memo(
    conn: sqlite3.Connection,
    case_id: str,
    today: date,
    run_id: str | None = None,
) -> dict:
    cases.require_case(conn, case_id)
    if run_id is None:
        run_id = _latest_completed_run(conn, case_id)
    if run_id is None:
        raise ClearanceError("Record facts before evaluating this case.")
    stored = _domain_facts(conn, run_id)
    decision = recommend(stored, today)
    sheet = shop(stored, today)
    carrier, premium = _carrier_premium(decision.recommendation, sheet)
    found = _conflict_payload(decision.conflicts)
    memo = {
        "recommendation": decision.recommendation,
        "reasons": list(decision.reasons),
        "missing": list(decision.missing),
        "conflicts": found,
        "carrier": carrier,
        "premium": premium,
    }
    conn.execute(
        """
        INSERT INTO memos (
            id, case_id, run_id, recommendation, reasons_json, missing_json,
            conflicts_json, carrier, premium, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid4().hex,
            case_id,
            run_id,
            memo["recommendation"],
            json.dumps(memo["reasons"]),
            json.dumps(memo["missing"]),
            json.dumps(memo["conflicts"]),
            carrier,
            premium,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    return memo


def assess(conn: sqlite3.Connection, run_id: str, today: date) -> dict:
    stored = _domain_facts(conn, run_id)
    decision = recommend(stored, today)
    sheet = shop(stored, today)
    carrier, premium = _carrier_premium(decision.recommendation, sheet)
    return {
        "recommendation": decision.recommendation,
        "reasons": list(decision.reasons),
        "missing": list(decision.missing),
        "conflicts": _conflict_payload(decision.conflicts),
        "carrier": carrier,
        "premium": premium,
        "offers": [
            {
                "carrier": offer.carrier,
                "premium": offer.premium,
                "status": offer.status,
                "reason": offer.reason,
            }
            for offer in sheet.offers
        ],
    }


def evaluate(conn: sqlite3.Connection, case_id: str, today: date) -> dict:
    memo = build_memo(conn, case_id, today)
    run_id = _latest_completed_run(conn, case_id)
    sheet = assess(conn, run_id or "", today)
    return {**memo, "offers": sheet["offers"]}


def present(conn: sqlite3.Connection, case_id: str) -> dict:
    view = cases.get_case(conn, case_id)
    from app.services.book import policy_for_case

    view["policy"] = policy_for_case(conn, case_id)
    run_id = _latest_completed_run(conn, case_id)
    if run_id is None:
        return view
    rows = _fact_rows(conn, run_id)
    stored = [_row_fact(row) for row in rows]
    view["facts"] = [
        {
            "id": row["id"],
            "name": row["name"],
            "value": row["value"],
            "document_id": row["document_id"],
            "quote": row["quote"],
        }
        for row in rows
    ]
    view["conflicts"] = _conflict_payload(conflicts(stored))
    view["memo"] = _memo_for_run(conn, run_id)
    return view


def _parse_fact(conn: sqlite3.Connection, case_id: str, item: Mapping[str, str]) -> Fact:
    name = str(item.get("name", "")).strip()
    value = str(item.get("value", "")).strip()
    document_id = str(item.get("document_id", "")).strip()
    quote = str(item.get("quote", ""))
    if not name:
        raise ClearanceError("A fact needs a name.")
    if name not in FACT_NAMES:
        raise ClearanceError(f"{name} is not a clearance fact.")
    if not value:
        raise ClearanceError("A fact needs a value.")
    if not document_id or not quote.strip():
        raise ClearanceError("A fact needs a citation.")
    _check_shape(name, value)
    body = _document_body(conn, case_id, document_id)
    if _collapse(quote) not in _collapse(body):
        raise ClearanceError("The citation is not in the document.")
    if _collapse(value) not in _collapse(quote):
        raise ClearanceError("The value is not in the cited text.")
    return Fact(name, value, document_id, quote)


def _check_shape(name: str, value: str) -> None:
    if name in DATE_FACTS:
        try:
            date.fromisoformat(value)
        except ValueError:
            raise ClearanceError(f"{name} is not a date.") from None
    if name in INT_FACTS:
        try:
            int(value)
        except ValueError:
            raise ClearanceError(f"{name} is not a whole number.") from None


def _document_body(conn: sqlite3.Connection, case_id: str, document_id: str) -> str:
    row = conn.execute(
        "SELECT case_id, body_text FROM documents WHERE id = ?",
        (document_id,),
    ).fetchone()
    if row is None:
        raise ClearanceError("The citation does not name a document on this case.")
    if row["case_id"] != case_id:
        raise ClearanceError("The citation names a document from another case.")
    return row["body_text"]


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _manual_run(conn: sqlite3.Connection, case_id: str) -> str:
    run_id = uuid4().hex
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO runs (
            id, case_id, prompt_version, model, status, started_at, finished_at
        ) VALUES (?, ?, ?, ?, 'completed', ?, ?)
        """,
        (run_id, case_id, MANUAL_PROMPT, MANUAL_MODEL, now, now),
    )
    return run_id


def _latest_completed_run(conn: sqlite3.Connection, case_id: str) -> str | None:
    row = conn.execute(
        """
        SELECT id FROM runs
        WHERE case_id = ? AND status = 'completed'
        ORDER BY rowid DESC
        LIMIT 1
        """,
        (case_id,),
    ).fetchone()
    if row is None:
        return None
    return row["id"]


def _fact_rows(conn: sqlite3.Connection, run_id: str) -> list[sqlite3.Row]:
    return list(conn.execute(
        """
        SELECT id, name, value, document_id, quote
        FROM facts
        WHERE run_id = ?
        ORDER BY rowid
        """,
        (run_id,),
    ))


def _domain_facts(conn: sqlite3.Connection, run_id: str) -> list[Fact]:
    return [_row_fact(row) for row in _fact_rows(conn, run_id)]


def _row_fact(row: sqlite3.Row) -> Fact:
    return Fact(row["name"], row["value"], row["document_id"], row["quote"])


def memo_for_run(conn: sqlite3.Connection, run_id: str | None) -> dict | None:
    if not run_id:
        return None
    return _memo_for_run(conn, run_id)


def _memo_for_run(conn: sqlite3.Connection, run_id: str) -> dict | None:
    row = conn.execute(
        """
        SELECT recommendation, reasons_json, missing_json, conflicts_json, carrier, premium
        FROM memos
        WHERE run_id = ?
        ORDER BY rowid DESC
        LIMIT 1
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "recommendation": row["recommendation"],
        "reasons": json.loads(row["reasons_json"]),
        "missing": json.loads(row["missing_json"]),
        "conflicts": json.loads(row["conflicts_json"]),
        "carrier": row["carrier"],
        "premium": row["premium"],
    }


def _carrier_premium(recommendation: str, sheet) -> tuple[str | None, float | None]:
    if recommendation not in {"quote", "refer"} or sheet.best is None:
        return None, None
    if recommendation == "quote" and sheet.best.status != "quoted":
        return None, None
    return sheet.best.carrier, sheet.best.premium


def _conflict_payload(found: Sequence[Conflict]) -> list[dict]:
    return [
        {
            "field": item.field,
            "values": [
                {
                    "value": value.value,
                    "document_id": value.document_id,
                    "quote": value.quote,
                }
                for value in item.values
            ],
        }
        for item in found
    ]
