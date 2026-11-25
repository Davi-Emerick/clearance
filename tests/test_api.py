import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import connect, db_path, init_db
from app.main import app


@pytest.fixture
def api():
    with TestClient(app) as client:
        yield client


def test_startup_creates_the_database_file(api, clearance_db):
    assert clearance_db.exists()
    response = api.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_the_demo_database_is_data_clearance_db(monkeypatch):
    monkeypatch.delenv("CLEARANCE_DB", raising=False)
    assert db_path() == Path(__file__).resolve().parents[1] / "data" / "clearance.db"


def test_a_case_stores_a_text_document_and_reads_it_back(api):
    created = api.post("/cases")
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "open"
    assert body["id"]
    assert body["created_at"]
    case_id = body["id"]

    first = api.post(
        f"/cases/{case_id}/documents",
        json={"name": " license.txt ", "body_text": "License number S10000023\n"},
    )
    second = api.post(
        f"/cases/{case_id}/documents",
        json={"name": "registration.txt", "body_text": "VIN 1FAKE0HALE0CAR001"},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    first_id = first.json()["id"]
    second_id = second.json()["id"]
    assert first.json()["name"] == "license.txt"

    case = api.get(f"/cases/{case_id}")
    assert case.status_code == 200
    found = case.json()
    assert found["status"] == "open"
    assert found["documents"] == [
        {"id": first_id, "name": "license.txt"},
        {"id": second_id, "name": "registration.txt"},
    ]
    assert found["facts"] == []
    assert found["conflicts"] == []
    assert found["memo"] is None

    document = api.get(f"/cases/{case_id}/documents/{first_id}")
    assert document.status_code == 200
    assert document.json()["body_text"] == "License number S10000023\n"


def test_a_missing_case_is_not_found(api):
    missing = api.get("/cases/missing")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Case not found."
    uploaded = api.post(
        "/cases/missing/documents",
        json={"name": "note.txt", "body_text": "hello"},
    )
    assert uploaded.status_code == 404
    assert uploaded.json()["detail"] == "Case not found."


def test_a_missing_document_is_not_found(api):
    case_id = api.post("/cases").json()["id"]
    response = api.get(f"/cases/{case_id}/documents/missing")
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found."


def test_a_document_from_another_case_is_not_found(api):
    first = api.post("/cases").json()["id"]
    second = api.post("/cases").json()["id"]
    document_id = api.post(
        f"/cases/{first}/documents",
        json={"name": "license.txt", "body_text": "S10000023"},
    ).json()["id"]
    response = api.get(f"/cases/{second}/documents/{document_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found."


def test_a_document_needs_a_name(api):
    case_id = api.post("/cases").json()["id"]
    response = api.post(
        f"/cases/{case_id}/documents",
        json={"name": "   ", "body_text": "hello"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "The document name is required."


def test_a_document_with_no_case_fails(clearance_db):
    conn = connect(clearance_db)
    try:
        init_db(conn)
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO documents (id, case_id, name, body_text) VALUES (?, ?, ?, ?)",
                ("doc-1", "missing-case", "license.txt", "S10000023"),
            )
    finally:
        conn.close()
