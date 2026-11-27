from fastapi.testclient import TestClient

from app.db import connect
from app.main import app

TODAY = "2026-06-15"
DEMOS = {
    "marcus-hale": ["license.txt", "registration.txt"],
    "helen-brooks": ["license.txt"],
    "injection-note": ["license.txt", "note.txt"],
}


def test_the_desk_is_one_column_of_local_files():
    with TestClient(app) as client:
        page = client.get("/")
        script = client.get("/static/desk.js")
        styles = client.get("/static/styles.css")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert "<h1>Get an auto quote</h1>" in page.text
    assert ">Clearance<" in page.text
    assert ">Bind<" in page.text
    assert ">Close<" in page.text
    assert 'src="/static/desk.js"' in page.text
    assert "http" not in page.text.split('src="/static/desk.js"')[0].split("<script")[-1]
    assert "@keyframes" not in styles.text
    assert "animation" not in styles.text
    assert script.status_code == 200
    assert "/cases/" in script.text
    assert "/bind?today=" in script.text
    assert "/close" in script.text
    assert "/runs/" in script.text
    assert "marcus-hale" in script.text
    assert "helen-brooks" in script.text
    assert "injection-note" in script.text


MARCUS = {
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

LABELS = (
    "Insured name",
    "License number",
    "License issued",
    "License expires",
    "VIN",
    "Plate",
    "Vehicle year",
    "Prior policy expires",
    "SDIP points",
    "Line of business",
)

SENTENCES = (
    "This file can be quoted.",
    "You can bind it.",
    "A person has to look at this file before anyone binds it.",
    "Do not bind this file.",
    "The folder is not complete.",
    "This is not an auto file.",
)


def test_the_form_is_on_the_page():
    with TestClient(app) as client:
        page = client.get("/")
        script = client.get("/static/desk.js")
    assert page.status_code == 200
    for label in LABELS:
        assert label in page.text
    assert "Continue" in page.text
    assert "See your quote" in script.text
    assert "Driver" in page.text
    assert "Vehicle" in page.text
    assert "Record" in page.text
    assert "YYYY-MM-DD" in page.text
    assert "15 June 2026" in page.text
    assert "Marcus Hale" in page.text
    assert "Helen Brooks" in page.text
    assert "Injection note" in page.text
    for sentence in SENTENCES:
        assert sentence in script.text


def test_a_typed_marcus_file_quotes_and_binds(monkeypatch, clearance_db):
    monkeypatch.setenv("CLEARANCE_MODEL", "fake")
    monkeypatch.setattr("httpx.post", _fail_if_called)
    with TestClient(app) as client:
        case_id = _post_application(client, MARCUS)
        folder = client.get(f"/cases/{case_id}")
        memo = folder.json()["memo"]
        assert memo["recommendation"] == "quote"
        assert memo["carrier"] == "Northglass Auto"
        assert memo["premium"] == 738.00
        bound = client.post(f"/cases/{case_id}/bind", params={"today": TODAY})
        assert bound.status_code == 200
        assert _policies(clearance_db, case_id) == 1


def test_a_typed_expired_license_declines_and_does_not_bind(monkeypatch, clearance_db):
    monkeypatch.setenv("CLEARANCE_MODEL", "fake")
    monkeypatch.setattr("httpx.post", _fail_if_called)
    fields = dict(MARCUS)
    fields["license_expires_on"] = "2024-01-01"
    with TestClient(app) as client:
        case_id = _post_application(client, fields)
        memo = client.get(f"/cases/{case_id}").json()["memo"]
        assert memo["recommendation"] == "decline"
        refused = client.post(f"/cases/{case_id}/bind", params={"today": TODAY})
        assert refused.status_code == 400
        assert refused.json()["detail"] == "Only a quote can be bound."
        assert _policies(clearance_db, case_id) == 0


def _fail_if_called(*_args, **_kwargs):
    raise AssertionError("The desk called the network.")


def _application(fields: dict[str, str]) -> str:
    return "\n".join(f"{name}: {value}" for name, value in fields.items() if value)


def _post_application(client: TestClient, fields: dict[str, str]) -> str:
    created = client.post("/cases")
    assert created.status_code == 201
    case_id = created.json()["id"]
    uploaded = client.post(
        f"/cases/{case_id}/documents",
        json={"name": "application.txt", "body_text": _application(fields)},
    )
    assert uploaded.status_code == 201
    run = client.post(f"/cases/{case_id}/run", params={"today": TODAY})
    assert run.status_code == 200
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


def test_the_page_can_load_the_three_folders(monkeypatch):
    monkeypatch.setenv("CLEARANCE_MODEL", "fake")

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("The desk called the network.")

    monkeypatch.setattr("httpx.post", fail_if_called)
    with TestClient(app) as client:
        marcus = _open_demo(client, "marcus-hale")
        assert marcus["memo"]["recommendation"] == "quote"
        assert marcus["memo"]["premium"] == 738.00
        assert marcus["memo"]["carrier"] == "Northglass Auto"
        assert marcus["facts"]
        assert marcus["facts"][0]["quote"]
        assert marcus["steps"]
        bound = client.post(f"/cases/{marcus['case_id']}/bind", params={"today": TODAY})
        assert bound.status_code == 200
        assert bound.json()["expires_on"] == "2027-06-15"

        helen = _open_demo(client, "helen-brooks")
        assert helen["memo"]["recommendation"] == "decline"
        refused = client.post(f"/cases/{helen['case_id']}/bind", params={"today": TODAY})
        assert refused.status_code == 400
        assert refused.json()["detail"] == "Only a quote can be bound."

        injection = _open_demo(client, "injection-note")
        assert injection["memo"]["recommendation"] == "decline"
        assert injection["memo"]["premium"] is None
        assert injection["memo"]["premium"] != 1
        note = next(item for item in injection["documents"] if item["name"] == "note.txt")
        assert "premium 1.00" in note["body_text"]
        opened = injection["steps"][0]
        assert opened["position"] == 1
        assert opened["request"]
        assert opened["response"] is not None


def _open_demo(client: TestClient, slug: str) -> dict:
    created = client.post("/cases")
    assert created.status_code == 201
    case_id = created.json()["id"]
    for name in DEMOS[slug]:
        body = client.get(f"/dossiers/{slug}/documents/{name}")
        assert body.status_code == 200
        uploaded = client.post(
            f"/cases/{case_id}/documents",
            json={"name": name, "body_text": body.text},
        )
        assert uploaded.status_code == 201
    run = client.post(f"/cases/{case_id}/run", params={"today": TODAY})
    assert run.status_code == 200
    folder = client.get(f"/cases/{case_id}")
    assert folder.status_code == 200
    documents = []
    for item in folder.json()["documents"]:
        document = client.get(f"/cases/{case_id}/documents/{item['id']}")
        assert document.status_code == 200
        documents.append(document.json())
    trace = client.get(f"/runs/{run.json()['run_id']}")
    assert trace.status_code == 200
    payload = folder.json()
    payload["case_id"] = case_id
    payload["documents"] = documents
    payload["steps"] = trace.json()["steps"]
    return payload
