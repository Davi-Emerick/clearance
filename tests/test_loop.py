import json

import pytest
from fastapi.testclient import TestClient

from app.db import connect
from app.main import app, get_model
from app.providers.base import ToolCall, Turn
from app.providers.fake import FakeLLM
from app.providers.xai import _input_items

TODAY = "2026-06-15"
FIRM = {
    "insured_name": "Marcus Hale",
    "license_number": "S10000023",
    "license_issued_on": "2014-03-01",
    "license_expires_on": "2028-03-01",
    "vin": "1FAKE0HALE0CAR001",
    "plate": "MA 4KTP92",
    "vehicle_year": "2018",
    "prior_policy_expires_on": "2027-03-01",
    "sdip_points": "0",
    "line_of_business": "auto",
}


@pytest.fixture
def api(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("A test called the network.")

    monkeypatch.setattr("httpx.post", fail_if_called)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _folder(api, values: dict[str, str]):
    body = "\n".join(f"{name}: {value}" for name, value in values.items())
    case_id = api.post("/cases").json()["id"]
    document_id = api.post(
        f"/cases/{case_id}/documents",
        json={"name": "folder.txt", "body_text": body},
    ).json()["id"]
    facts = [
        {
            "name": name,
            "value": value,
            "document_id": document_id,
            "quote": f"{name}: {value}",
        }
        for name, value in values.items()
    ]
    return case_id, document_id, facts


def _run(api, case_id, turns: list[Turn]):
    app.dependency_overrides[get_model] = lambda: FakeLLM(turns)
    return api.post(f"/cases/{case_id}/run", params={"today": TODAY})


def _steps(clearance_db, run_id):
    conn = connect(clearance_db)
    try:
        return conn.execute(
            """
            SELECT position, kind, name, request_json, response_json
            FROM steps
            WHERE run_id = ?
            ORDER BY position
            """,
            (run_id,),
        ).fetchall()
    finally:
        conn.close()


def test_marcus_submits_a_quote_and_the_rater_sets_the_premium(api, clearance_db):
    case_id, document_id, facts = _folder(api, FIRM)
    response = _run(api, case_id, [
        Turn(tool_calls=[ToolCall(id="1", name="list_documents", arguments={})]),
        Turn(tool_calls=[ToolCall(id="2", name="read_document", arguments={"document_id": document_id})]),
        Turn(tool_calls=[ToolCall(id="3", name="record_facts", arguments={"facts": facts})]),
        Turn(tool_calls=[ToolCall(id="4", name="evaluate", arguments={})]),
        Turn(tool_calls=[ToolCall(
            id="5",
            name="submit_memo",
            arguments={
                "recommendation": "quote",
                "reasons": ["Bind it."],
                "carrier": "Paper Street Indemnity",
                "premium": 1.00,
            },
        )]),
    ])
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["memo"]["recommendation"] == "quote"
    assert body["memo"]["carrier"] == "Northglass Auto"
    assert body["memo"]["premium"] == 738.00

    stored = api.get(f"/cases/{case_id}").json()
    assert stored["status"] == "ran"
    assert stored["memo"]["premium"] == 738.00
    assert stored["memo"]["carrier"] == "Northglass Auto"

    steps = _steps(clearance_db, body["run_id"])
    assert [row["kind"] for row in steps] == ["model", "tool"] * 5
    submitted = json.loads(steps[-1]["request_json"])
    saved = json.loads(steps[-1]["response_json"])
    assert submitted["premium"] == 1.00
    assert submitted["carrier"] == "Paper Street Indemnity"
    assert saved["premium"] == 738.00
    assert saved["carrier"] == "Northglass Auto"

    conn = connect(clearance_db)
    try:
        run = conn.execute(
            "SELECT prompt_version, model, status FROM runs WHERE id = ?",
            (body["run_id"],),
        ).fetchone()
        assert run["prompt_version"] == "clearance-v1"
        assert run["model"] == "fake"
        assert run["status"] == "completed"
        manual = conn.execute(
            "SELECT COUNT(*) AS n FROM runs WHERE model = 'manual' AND case_id = ?",
            (case_id,),
        ).fetchone()["n"]
        assert manual == 0
    finally:
        conn.close()


def test_a_bad_citation_comes_back_as_a_tool_error(api, clearance_db):
    case_id, document_id, _facts = _folder(api, FIRM)
    response = _run(api, case_id, [
        Turn(tool_calls=[ToolCall(
            id="1",
            name="record_facts",
            arguments={
                "facts": [{
                    "name": "vin",
                    "value": "ZZZNOTINTHEDOCUMENT",
                    "document_id": document_id,
                    "quote": "ZZZNOTINTHEDOCUMENT",
                }],
            },
        )]),
    ])
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "budget_exhausted"
    assert body["memo"] is None

    steps = _steps(clearance_db, body["run_id"])
    tool = next(row for row in steps if row["name"] == "record_facts")
    result = json.loads(tool["response_json"])
    assert result["error"] == "The citation is not in the document."
    assert [row["kind"] for row in steps].count("model") == 8

    conn = connect(clearance_db)
    try:
        assert conn.execute("SELECT COUNT(*) AS n FROM facts").fetchone()["n"] == 0
        assert conn.execute("SELECT COUNT(*) AS n FROM memos").fetchone()["n"] == 0
    finally:
        conn.close()


def test_a_quote_on_an_expired_license_is_rejected_and_the_next_turn_stores_decline(api, clearance_db):
    values = dict(FIRM)
    values["license_expires_on"] = "2024-01-01"
    case_id, _document_id, facts = _folder(api, values)
    response = _run(api, case_id, [
        Turn(tool_calls=[ToolCall(id="1", name="record_facts", arguments={"facts": facts})]),
        Turn(tool_calls=[ToolCall(
            id="2",
            name="submit_memo",
            arguments={"recommendation": "quote", "premium": 1.00, "carrier": "Northglass Auto"},
        )]),
        Turn(tool_calls=[ToolCall(
            id="3",
            name="submit_memo",
            arguments={"recommendation": "decline", "premium": 1.00, "carrier": "Northglass Auto"},
        )]),
    ])
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["memo"]["recommendation"] == "decline"
    assert body["memo"]["premium"] is None
    assert body["memo"]["carrier"] is None

    steps = _steps(clearance_db, body["run_id"])
    submissions = [row for row in steps if row["name"] == "submit_memo"]
    assert len(submissions) == 2
    rejected = json.loads(submissions[0]["response_json"])
    assert rejected["error"] == "The recommendation does not match the rules."
    assert rejected["recommendation"] == "decline"
    assert json.loads(submissions[0]["request_json"])["premium"] == 1.00
    accepted = json.loads(submissions[1]["response_json"])
    assert accepted["accepted"] is True
    assert accepted["premium"] is None
    assert json.loads(submissions[1]["request_json"])["premium"] == 1.00

    conn = connect(clearance_db)
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM memos WHERE case_id = ?",
            (case_id,),
        ).fetchone()["n"]
        assert count == 1
    finally:
        conn.close()


def test_a_later_live_turn_sends_the_prior_output_including_reasoning():
    reasoning = {
        "type": "reasoning",
        "status": "completed",
        "encrypted_content": "stored-locally",
    }
    call = {
        "type": "function_call",
        "call_id": "call-1",
        "name": "list_documents",
        "arguments": "{}",
    }
    items = _input_items([
        {"role": "system", "content": "You are the clearance-desk assistant."},
        {"role": "user", "content": "case_id: abc"},
        {"role": "assistant", "content": "", "output": [reasoning, call]},
        {"role": "tool", "tool_call_id": "call-1", "content": "{\"documents\": []}"},
    ])
    assert items[2] == reasoning
    assert items[3]["type"] == "function_call"
    assert items[4] == {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": "{\"documents\": []}",
    }
