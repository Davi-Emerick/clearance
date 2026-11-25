import sqlite3
from datetime import date

from app.errors import ClearanceError
from app.services import cases, clearance

TOOLS = (
    {
        "name": "list_documents",
        "description": "List the document names and ids on this case. The body is not included.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "read_document",
        "description": "Read the body of one document on this case.",
        "parameters": {
            "type": "object",
            "properties": {"document_id": {"type": "string"}},
            "required": ["document_id"],
        },
    },
    {
        "name": "record_facts",
        "description": "Store the cited fact set for this run. A later call replaces that draft.",
        "parameters": {
            "type": "object",
            "properties": {
                "facts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "value": {"type": "string"},
                            "document_id": {"type": "string"},
                            "quote": {"type": "string"},
                        },
                        "required": ["name", "value", "document_id", "quote"],
                    },
                }
            },
            "required": ["facts"],
        },
    },
    {
        "name": "evaluate",
        "description": "Return the only legal recommendation and the six offers. This does not store a memo.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "submit_memo",
        "description": "Store the memo when the recommendation matches evaluate. The premium is the rater's number.",
        "parameters": {
            "type": "object",
            "properties": {
                "recommendation": {"type": "string"},
                "reasons": {"type": "array", "items": {"type": "string"}},
                "missing": {"type": "array", "items": {"type": "string"}},
                "conflicts": {"type": "array"},
                "carrier": {"type": "string"},
                "premium": {"type": "number"},
            },
            "required": ["recommendation"],
        },
    },
)


def call_tool(
    conn: sqlite3.Connection,
    case_id: str,
    run_id: str,
    today: date,
    name: str,
    arguments: dict,
) -> dict:
    try:
        if name == "list_documents":
            return _list_documents(conn, case_id)
        if name == "read_document":
            return _read_document(conn, case_id, arguments)
        if name == "record_facts":
            return _record_facts(conn, case_id, run_id, arguments)
        if name == "evaluate":
            return _evaluate(conn, run_id, today)
        if name == "submit_memo":
            return _submit_memo(conn, case_id, run_id, today, arguments)
        return {"error": f"Unknown tool {name}."}
    except ClearanceError as exc:
        return {"error": exc.message}


def _list_documents(conn: sqlite3.Connection, case_id: str) -> dict:
    view = cases.get_case(conn, case_id)
    return {"documents": view["documents"]}


def _read_document(conn: sqlite3.Connection, case_id: str, arguments: dict) -> dict:
    document_id = str(arguments.get("document_id", "")).strip()
    if not document_id:
        raise ClearanceError("A document id is required.")
    return cases.get_document(conn, case_id, document_id)


def _record_facts(conn: sqlite3.Connection, case_id: str, run_id: str, arguments: dict) -> dict:
    submitted = arguments.get("facts") or []
    parsed = clearance.checked_facts(conn, case_id, submitted)
    clearance.write_facts(conn, case_id, run_id, parsed)
    return {"stored": len(parsed)}


def _evaluate(conn: sqlite3.Connection, run_id: str, today: date) -> dict:
    return clearance.assess(conn, run_id, today)


def _submit_memo(
    conn: sqlite3.Connection,
    case_id: str,
    run_id: str,
    today: date,
    arguments: dict,
) -> dict:
    legal = clearance.assess(conn, run_id, today)
    submitted = str(arguments.get("recommendation", "")).strip()
    if submitted != legal["recommendation"]:
        return {
            "error": "The recommendation does not match the rules.",
            "recommendation": legal["recommendation"],
            "reasons": legal["reasons"],
            "missing": legal["missing"],
            "conflicts": legal["conflicts"],
            "carrier": legal["carrier"],
            "premium": legal["premium"],
        }
    memo = clearance.build_memo(conn, case_id, today, run_id)
    return {"accepted": True, **memo}
