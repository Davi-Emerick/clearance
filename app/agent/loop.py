import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from app.agent.tools import TOOLS, call_tool
from app.errors import ClearanceError
from app.providers.base import Model
from app.services import cases

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "clearance-v1.md"
PROMPT_VERSION = "clearance-v1"
BUDGET = 8
NUDGE = "Call evaluate or submit_memo."


class RunFailed(Exception):
    def __init__(self, run_id: str):
        super().__init__(run_id)
        self.run_id = run_id


def read_run(conn: sqlite3.Connection, run_id: str) -> dict:
    row = conn.execute(
        """
        SELECT id, case_id, prompt_version, model, status, started_at, finished_at
        FROM runs
        WHERE id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        raise ClearanceError("Run not found.", 404)
    steps = conn.execute(
        """
        SELECT position, kind, name, request_json, response_json, latency_ms
        FROM steps
        WHERE run_id = ?
        ORDER BY position
        """,
        (run_id,),
    ).fetchall()
    return {
        "id": row["id"],
        "case_id": row["case_id"],
        "prompt_version": row["prompt_version"],
        "model": row["model"],
        "status": row["status"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "steps": [
            {
                "position": step["position"],
                "kind": step["kind"],
                "name": step["name"],
                "request": json.loads(step["request_json"]),
                "response": json.loads(step["response_json"]),
                "latency_ms": step["latency_ms"],
            }
            for step in steps
        ],
    }


def run_case(conn: sqlite3.Connection, case_id: str, model: Model, today: date) -> dict:
    cases.require_case(conn, case_id)
    run_id = _open_run(conn, case_id, getattr(model, "model_id", "fake"))
    try:
        return _drive(conn, case_id, run_id, model, today)
    except Exception as exc:
        _finish(conn, run_id, "failed", case_id)
        raise RunFailed(run_id) from exc


def _drive(
    conn: sqlite3.Connection,
    case_id: str,
    run_id: str,
    model: Model,
    today: date,
) -> dict:
    messages: list[dict] = [
        {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
        {"role": "user", "content": f"case_id: {case_id}"},
    ]
    memo = None
    position = 0
    for _step in range(BUDGET):
        started = perf_counter()
        turn = model.complete(messages, TOOLS)
        position = _step_row(
            conn,
            run_id,
            position,
            "model",
            getattr(model, "model_id", "fake"),
            {"messages": messages, "tools": [tool["name"] for tool in TOOLS]},
            turn.model_dump(),
            started,
        )
        messages.append({
            "role": "assistant",
            "content": turn.text,
            "tool_calls": [call.model_dump() for call in turn.tool_calls],
            "output": turn.output,
        })
        if not turn.tool_calls:
            messages.append({"role": "user", "content": NUDGE})
            continue
        for call in turn.tool_calls:
            started = perf_counter()
            result = call_tool(conn, case_id, run_id, today, call.name, call.arguments)
            position = _step_row(
                conn,
                run_id,
                position,
                "tool",
                call.name,
                call.arguments,
                result,
                started,
            )
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result),
            })
            if call.name == "submit_memo" and result.get("accepted"):
                _finish(conn, run_id, "completed", case_id)
                return {"run_id": run_id, "status": "completed", "memo": _public_memo(result)}
    _finish(conn, run_id, "budget_exhausted", case_id)
    return {"run_id": run_id, "status": "budget_exhausted", "memo": memo}


def _public_memo(result: dict) -> dict:
    return {
        "recommendation": result["recommendation"],
        "reasons": result["reasons"],
        "missing": result["missing"],
        "conflicts": result["conflicts"],
        "carrier": result["carrier"],
        "premium": result["premium"],
    }


def _open_run(conn: sqlite3.Connection, case_id: str, model_name: str) -> str:
    run_id = uuid4().hex
    conn.execute(
        """
        INSERT INTO runs (
            id, case_id, prompt_version, model, status, started_at, finished_at
        ) VALUES (?, ?, ?, ?, 'failed', ?, NULL)
        """,
        (run_id, case_id, PROMPT_VERSION, model_name, _now()),
    )
    return run_id


def _finish(conn: sqlite3.Connection, run_id: str, status: str, case_id: str) -> None:
    conn.execute(
        "UPDATE runs SET status = ?, finished_at = ? WHERE id = ?",
        (status, _now(), run_id),
    )
    if status in {"completed", "budget_exhausted"}:
        conn.execute("UPDATE cases SET status = 'ran' WHERE id = ?", (case_id,))


def _step_row(
    conn: sqlite3.Connection,
    run_id: str,
    position: int,
    kind: str,
    name: str,
    request: object,
    response: object,
    started: float,
) -> int:
    position += 1
    conn.execute(
        """
        INSERT INTO steps (
            run_id, position, kind, name, request_json, response_json, latency_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            position,
            kind,
            name,
            json.dumps(request),
            json.dumps(response),
            max(0, int((perf_counter() - started) * 1000)),
        ),
    )
    return position


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
