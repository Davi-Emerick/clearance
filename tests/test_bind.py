import pytest
from fastapi.testclient import TestClient

from app.agent.tools import TOOLS
from app.db import connect
from app.domain.facts import Fact
from app.main import app
from app.services.clearance import write_facts

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


def _quote(api, values: dict[str, str] | None = None, today: str = TODAY):
    fields = dict(FIRM if values is None else values)
    body = "\n".join(f"{name}: {value}" for name, value in fields.items())
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
        for name, value in fields.items()
    ]
    recorded = api.post(f"/cases/{case_id}/facts", params={"today": today}, json=facts)
    assert recorded.status_code == 201
    return case_id


def _policies(clearance_db, case_id: str) -> int:
    conn = connect(clearance_db)
    try:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM policies WHERE case_id = ?",
            (case_id,),
        ).fetchone()["n"]
    finally:
        conn.close()


def test_the_agent_has_no_bind_tool():
    assert "bind" not in {tool["name"] for tool in TOOLS}
    assert "close" not in {tool["name"] for tool in TOOLS}


def test_a_quote_binds_through_the_anniversary(api, clearance_db):
    case_id = _quote(api)
    response = api.post(f"/cases/{case_id}/bind", params={"today": TODAY})
    assert response.status_code == 200
    policy = response.json()
    assert policy["status"] == "bound"
    assert policy["insured_name"] == "Marcus Hale"
    assert policy["carrier"] == "Northglass Auto"
    assert policy["premium"] == 738.00
    assert policy["effective_on"] == "2026-06-15"
    assert policy["expires_on"] == "2027-06-15"
    assert _policies(clearance_db, case_id) == 1
    assert api.get(f"/cases/{case_id}").json()["policy"]["id"] == policy["id"]

    again = api.post(f"/cases/{case_id}/bind", params={"today": TODAY})
    assert again.status_code == 400
    assert again.json()["detail"] == "This case is already bound."
    assert _policies(clearance_db, case_id) == 1


def test_a_leap_day_term_ends_on_28_february(api):
    case_id = _quote(api, today="2024-02-29")
    response = api.post(f"/cases/{case_id}/bind", params={"today": "2024-02-29"})
    assert response.status_code == 200
    assert response.json()["effective_on"] == "2024-02-29"
    assert response.json()["expires_on"] == "2025-02-28"
    assert response.json()["premium"] == 738.00


@pytest.mark.parametrize(
    ("changes", "recommendation"),
    [
        ({"license_expires_on": "2024-01-01"}, "decline"),
        ({"sdip_points": "4"}, "refer"),
        ({"vin": None}, "incomplete"),
        ({"line_of_business": "homeowners", "vin": None}, "out_of_scope"),
    ],
)
def test_a_memo_that_is_not_quote_does_not_bind(api, clearance_db, changes, recommendation):
    values = dict(FIRM)
    for name, value in changes.items():
        if value is None:
            values.pop(name)
        else:
            values[name] = value
    case_id = _quote(api, values)
    recorded = api.get(f"/cases/{case_id}").json()
    assert recorded["memo"]["recommendation"] == recommendation
    response = api.post(f"/cases/{case_id}/bind", params={"today": TODAY})
    assert response.status_code == 400
    assert response.json()["detail"] == "Only a quote can be bound."
    assert _policies(clearance_db, case_id) == 0


def test_bind_refuses_when_the_facts_change_after_the_quote(api, clearance_db):
    case_id = _quote(api)
    conn = connect(clearance_db)
    try:
        run_id = conn.execute(
            """
            SELECT id FROM runs
            WHERE case_id = ? AND status = 'completed'
            ORDER BY rowid DESC
            LIMIT 1
            """,
            (case_id,),
        ).fetchone()["id"]
        rows = conn.execute(
            "SELECT name, value, document_id, quote FROM facts WHERE run_id = ?",
            (run_id,),
        ).fetchall()
        facts = [
            Fact(
                row["name"],
                "2024-01-01" if row["name"] == "license_expires_on" else row["value"],
                row["document_id"],
                row["quote"],
            )
            for row in rows
        ]
        write_facts(conn, case_id, run_id, facts)
        conn.commit()
    finally:
        conn.close()

    assert api.get(f"/cases/{case_id}").json()["memo"]["recommendation"] == "quote"
    response = api.post(f"/cases/{case_id}/bind", params={"today": TODAY})
    assert response.status_code == 400
    assert response.json()["detail"] == "The rules no longer return quote."
    assert _policies(clearance_db, case_id) == 0


def test_a_zero_premium_does_not_bind(api, clearance_db):
    case_id = _quote(api)
    conn = connect(clearance_db)
    try:
        conn.execute("UPDATE memos SET premium = 0 WHERE case_id = ?", (case_id,))
        conn.commit()
    finally:
        conn.close()
    response = api.post(f"/cases/{case_id}/bind", params={"today": TODAY})
    assert response.status_code == 400
    assert response.json()["detail"] == "The premium must be greater than zero."
    assert _policies(clearance_db, case_id) == 0


def test_close_writes_no_policy(api, clearance_db):
    case_id = _quote(api, {"license_expires_on": "2024-01-01", **{k: v for k, v in FIRM.items() if k != "license_expires_on"}})
    response = api.post(f"/cases/{case_id}/close", json={"note": "The license is expired. The person stopped here."})
    assert response.status_code == 200
    assert response.json()["status"] == "closed"
    assert response.json()["note"] == "The license is expired. The person stopped here."
    assert _policies(clearance_db, case_id) == 0
    assert api.get(f"/cases/{case_id}").json()["policy"] is None


def test_run_without_a_model_choice_or_a_key_names_both_options(api, monkeypatch):
    monkeypatch.delenv("CLEARANCE_MODEL", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    case_id = api.post("/cases").json()["id"]
    response = api.post(f"/cases/{case_id}/run")
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "fake" in detail
    assert "live" in detail


def test_the_fake_model_runs_the_marcus_script_without_the_network(api, monkeypatch):
    monkeypatch.setenv("CLEARANCE_MODEL", "fake")
    case_id = _quote_folder_only(api)
    response = api.post(f"/cases/{case_id}/run", params={"today": TODAY})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["memo"]["recommendation"] == "quote"
    assert body["memo"]["carrier"] == "Northglass Auto"
    assert body["memo"]["premium"] == 738.00


def _quote_folder_only(api):
    body = "\n".join(f"{name}: {value}" for name, value in FIRM.items())
    case_id = api.post("/cases").json()["id"]
    uploaded = api.post(
        f"/cases/{case_id}/documents",
        json={"name": "folder.txt", "body_text": body},
    )
    assert uploaded.status_code == 201
    return case_id
