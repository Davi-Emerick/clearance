import sqlite3
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.db import connect, init_db
from app.domain.facts import Fact
from app.domain.rater import shop
from app.main import app
from app.services import cases

TODAY = "2026-06-15"
CLOCK = date(2026, 6, 15)
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
def api():
    with TestClient(app) as client:
        yield client


def _folder(api, lines: dict[str, str] | None = None):
    values = dict(FIRM if lines is None else lines)
    body = "\n".join(f"{name}: {value}" for name, value in values.items())
    case_id = api.post("/cases").json()["id"]
    document_id = api.post(
        f"/cases/{case_id}/documents",
        json={"name": "folder.txt", "body_text": body},
    ).json()["id"]
    facts = [
        {"name": name, "value": value, "document_id": document_id, "quote": f"{name}: {value}"}
        for name, value in values.items()
    ]
    return case_id, document_id, facts


def test_posted_facts_return_the_rater_premium(api):
    case_id, _document_id, facts = _folder(api)
    response = api.post(f"/cases/{case_id}/facts", params={"today": TODAY}, json=facts)
    assert response.status_code == 201
    memo = response.json()
    domain = [
        Fact(item["name"], item["value"], item["document_id"], item["quote"])
        for item in facts
    ]
    sheet = shop(domain, CLOCK)
    assert sheet.best is not None
    assert memo["recommendation"] == "quote"
    assert memo["carrier"] == "Northglass Auto"
    assert memo["premium"] == 738.00
    assert memo["premium"] == sheet.best.premium
    assert memo["carrier"] == sheet.best.carrier

    evaluated = api.post(f"/cases/{case_id}/evaluate", params={"today": TODAY})
    assert evaluated.status_code == 200
    body = evaluated.json()
    assert body["recommendation"] == "quote"
    assert body["premium"] == 738.00
    northglass = next(offer for offer in body["offers"] if offer["carrier"] == "Northglass Auto")
    assert northglass["premium"] == 738.00
    assert northglass["status"] == "quoted"

    stored = api.get(f"/cases/{case_id}")
    assert stored.status_code == 200
    assert stored.json()["memo"]["premium"] == 738.00
    assert stored.json()["memo"]["carrier"] == "Northglass Auto"
    assert len(stored.json()["facts"]) == len(facts)


def test_a_manual_fact_set_keeps_one_run(api, clearance_db):
    case_id, _document_id, facts = _folder(api)
    assert api.post(f"/cases/{case_id}/facts", params={"today": TODAY}, json=facts).status_code == 201
    conn = connect(clearance_db)
    try:
        rows = conn.execute(
            """
            SELECT facts.run_id, runs.model, runs.prompt_version, runs.status, runs.case_id
            FROM facts
            JOIN runs ON runs.id = facts.run_id
            """
        ).fetchall()
        assert len(rows) == len(facts)
        assert len({row["run_id"] for row in rows}) == 1
        assert rows[0]["model"] == "manual"
        assert rows[0]["prompt_version"] == "manual"
        assert rows[0]["status"] == "completed"
        assert rows[0]["case_id"] == case_id
    finally:
        conn.close()


def test_a_vin_missing_from_the_document_stores_nothing(api, clearance_db):
    case_id, document_id, facts = _folder(api)
    facts.append({
        "name": "vin",
        "value": "ZZZNOTINTHEDOCUMENT",
        "document_id": document_id,
        "quote": "ZZZNOTINTHEDOCUMENT",
    })
    response = api.post(f"/cases/{case_id}/facts", params={"today": TODAY}, json=facts)
    assert response.status_code == 400
    assert response.json()["detail"] == "The citation is not in the document."
    case = api.get(f"/cases/{case_id}")
    assert case.json()["facts"] == []
    assert case.json()["memo"] is None
    conn = connect(clearance_db)
    try:
        assert conn.execute("SELECT COUNT(*) AS n FROM facts").fetchone()["n"] == 0
        assert conn.execute("SELECT COUNT(*) AS n FROM runs").fetchone()["n"] == 0
        assert conn.execute("SELECT COUNT(*) AS n FROM memos").fetchone()["n"] == 0
    finally:
        conn.close()


def test_a_citation_outside_the_document_stores_nothing(api):
    case_id, document_id, facts = _folder(api)
    facts[0] = {
        "name": "insured_name",
        "value": "Marcus Hale",
        "document_id": document_id,
        "quote": "This sentence was not in the folder.",
    }
    response = api.post(f"/cases/{case_id}/facts", params={"today": TODAY}, json=facts)
    assert response.status_code == 400
    assert response.json()["detail"] == "The citation is not in the document."
    assert api.get(f"/cases/{case_id}").json()["facts"] == []


def test_a_value_outside_its_citation_stores_nothing(api):
    case_id, document_id, facts = _folder(api)
    facts[0]["value"] = "Elena Vargas"
    response = api.post(f"/cases/{case_id}/facts", params={"today": TODAY}, json=facts)
    assert response.status_code == 400
    assert response.json()["detail"] == "The value is not in the cited text."
    assert api.get(f"/cases/{case_id}").json()["facts"] == []


def test_collapsed_whitespace_still_cites_the_document(api):
    case_id = api.post("/cases").json()["id"]
    document_id = api.post(
        f"/cases/{case_id}/documents",
        json={"name": "license.txt", "body_text": "VIN:\n1FAKE0HALE0CAR001"},
    ).json()["id"]
    response = api.post(
        f"/cases/{case_id}/facts",
        params={"today": TODAY},
        json=[{
            "name": "vin",
            "value": "1FAKE0HALE0CAR001",
            "document_id": document_id,
            "quote": "VIN:  1FAKE0HALE0CAR001",
        }],
    )
    assert response.status_code == 201
    assert api.get(f"/cases/{case_id}").json()["facts"][0]["value"] == "1FAKE0HALE0CAR001"


def test_a_fact_without_a_citation_is_refused(api):
    case_id, _document_id, facts = _folder(api)
    facts[0]["quote"] = "   "
    response = api.post(f"/cases/{case_id}/facts", params={"today": TODAY}, json=facts)
    assert response.status_code == 400
    assert response.json()["detail"] == "A fact needs a citation."
    assert api.get(f"/cases/{case_id}").json()["facts"] == []


def test_a_document_from_another_case_is_refused(api):
    case_id, _document_id, facts = _folder(api)
    other = api.post("/cases").json()["id"]
    other_document = api.post(
        f"/cases/{other}/documents",
        json={"name": "other.txt", "body_text": facts[0]["quote"]},
    ).json()["id"]
    facts[0]["document_id"] = other_document
    response = api.post(f"/cases/{case_id}/facts", params={"today": TODAY}, json=facts)
    assert response.status_code == 400
    assert response.json()["detail"] == "The citation names a document from another case."
    assert api.get(f"/cases/{case_id}").json()["facts"] == []


def test_a_fact_without_a_run_fails(clearance_db):
    conn = connect(clearance_db)
    try:
        init_db(conn)
        case = cases.create_case(conn)
        document = cases.add_document(conn, case["id"], "license.txt", "VIN 1FAKE0HALE0CAR001")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO facts (id, case_id, run_id, name, value, document_id, quote)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "fact-1",
                    case["id"],
                    "missing-run",
                    "vin",
                    "1FAKE0HALE0CAR001",
                    document["id"],
                    "VIN 1FAKE0HALE0CAR001",
                ),
            )
    finally:
        conn.close()
