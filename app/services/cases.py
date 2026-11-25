import sqlite3
from datetime import datetime
from uuid import uuid4

from app.errors import ClearanceError


def create_case(conn: sqlite3.Connection) -> dict:
    case_id = uuid4().hex
    created_at = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO cases (id, created_at, status) VALUES (?, ?, 'open')",
        (case_id, created_at),
    )
    return {"id": case_id, "created_at": created_at, "status": "open"}


def add_document(conn: sqlite3.Connection, case_id: str, name: str, body_text: str) -> dict:
    cleaned = name.strip()
    if not cleaned:
        raise ClearanceError("The document name is required.")
    require_case(conn, case_id)
    document_id = uuid4().hex
    conn.execute(
        "INSERT INTO documents (id, case_id, name, body_text) VALUES (?, ?, ?, ?)",
        (document_id, case_id, cleaned, body_text),
    )
    return {"id": document_id, "case_id": case_id, "name": cleaned}


def get_case(conn: sqlite3.Connection, case_id: str) -> dict:
    row = require_case(conn, case_id)
    documents = conn.execute(
        "SELECT id, name FROM documents WHERE case_id = ? ORDER BY rowid",
        (case_id,),
    ).fetchall()
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "status": row["status"],
        "documents": [{"id": item["id"], "name": item["name"]} for item in documents],
        "facts": [],
        "conflicts": [],
        "memo": None,
    }


def get_document(conn: sqlite3.Connection, case_id: str, document_id: str) -> dict:
    require_case(conn, case_id)
    row = conn.execute(
        """
        SELECT id, case_id, name, body_text
        FROM documents
        WHERE id = ? AND case_id = ?
        """,
        (document_id, case_id),
    ).fetchone()
    if row is None:
        raise ClearanceError("Document not found.", 404)
    return {
        "id": row["id"],
        "case_id": row["case_id"],
        "name": row["name"],
        "body_text": row["body_text"],
    }


def require_case(conn: sqlite3.Connection, case_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT id, created_at, status FROM cases WHERE id = ?",
        (case_id,),
    ).fetchone()
    if row is None:
        raise ClearanceError("Case not found.", 404)
    return row
