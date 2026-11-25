import sqlite3
from datetime import date, datetime
from uuid import uuid4

from app.domain.facts import Fact, agreed
from app.errors import ClearanceError
from app.services import cases, clearance


def one_year_expiration(effective: date) -> date:
    """Anniversary date. Coverage runs up to, and not including, this day."""
    try:
        return effective.replace(year=effective.year + 1)
    except ValueError:
        return effective.replace(year=effective.year + 1, day=28)


def bind_case(conn: sqlite3.Connection, case_id: str, today: date) -> dict:
    row = cases.require_case(conn, case_id)
    if row["status"] == "bound":
        raise ClearanceError("This case is already bound.")
    run_id = _latest_completed_run(conn, case_id)
    memo = clearance.memo_for_run(conn, run_id) if run_id else None
    if memo is None or memo["recommendation"] != "quote":
        raise ClearanceError("Only a quote can be bound.")
    legal = clearance.assess(conn, run_id, today)
    if legal["recommendation"] != "quote":
        raise ClearanceError("The rules no longer return quote.")
    premium = memo["premium"]
    if premium is None or float(premium) <= 0:
        raise ClearanceError("The premium must be greater than zero.")
    carrier = memo["carrier"]
    if not carrier:
        raise ClearanceError("The quote has no carrier.")
    insured = agreed(_facts(conn, run_id), "insured_name")
    if not insured:
        raise ClearanceError("The insured's name is not in the file.")
    effective = today
    expires = one_year_expiration(effective)
    if expires <= effective:
        raise ClearanceError("The expiration date must be after the effective date.")
    policy_id = uuid4().hex
    bound_at = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO policies (
            id, case_id, insured_name, effective_on, expires_on, premium, carrier, bound_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            policy_id,
            case_id,
            insured,
            effective.isoformat(),
            expires.isoformat(),
            float(premium),
            carrier,
            bound_at,
        ),
    )
    conn.execute("UPDATE cases SET status = 'bound' WHERE id = ?", (case_id,))
    return {
        "id": policy_id,
        "case_id": case_id,
        "status": "bound",
        "insured_name": insured,
        "effective_on": effective.isoformat(),
        "expires_on": expires.isoformat(),
        "premium": float(premium),
        "carrier": carrier,
        "bound_at": bound_at,
    }


def close_case(conn: sqlite3.Connection, case_id: str, note: str) -> dict:
    row = cases.require_case(conn, case_id)
    if row["status"] == "bound":
        raise ClearanceError("This case is already bound.")
    cleaned = note.strip()
    if not cleaned:
        raise ClearanceError("A note is required.")
    conn.execute("UPDATE cases SET status = 'closed' WHERE id = ?", (case_id,))
    return {"id": case_id, "status": "closed", "note": cleaned}


def policy_for_case(conn: sqlite3.Connection, case_id: str) -> dict | None:
    row = conn.execute(
        """
        SELECT id, case_id, insured_name, effective_on, expires_on, premium, carrier, bound_at
        FROM policies
        WHERE case_id = ?
        ORDER BY rowid DESC
        LIMIT 1
        """,
        (case_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "case_id": row["case_id"],
        "insured_name": row["insured_name"],
        "effective_on": row["effective_on"],
        "expires_on": row["expires_on"],
        "premium": row["premium"],
        "carrier": row["carrier"],
        "bound_at": row["bound_at"],
    }


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


def _facts(conn: sqlite3.Connection, run_id: str) -> list[Fact]:
    rows = conn.execute(
        """
        SELECT name, value, document_id, quote
        FROM facts
        WHERE run_id = ?
        ORDER BY rowid
        """,
        (run_id,),
    ).fetchall()
    return [Fact(row["name"], row["value"], row["document_id"], row["quote"]) for row in rows]
