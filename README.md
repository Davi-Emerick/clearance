# Clearance

Clearance reads a new-business folder and writes a short memo: quote, refer, decline, incomplete, or out of scope. The premium and the recommendation come from Python rules. The model supplies cited facts and a memo that has to agree with those rules. A person binds the policy.

The people, the documents, and the carrier prices are fictional. Nothing in this repository is a real book of business, a government ID, or a filed rate.

SDIP in this project is points inside the window, not the legal Massachusetts worksheet.

Status: phase 6

This checkout answers `GET /health`, stores a case and its text documents, and accepts a cited fact set with no API key. `POST /cases/{id}/run` runs one loop of at most 8 model steps. `build_memo` is the only writer of a memo. The premium on that memo comes from `shop`. A person binds a quote with `POST /cases/{id}/bind`. The rules run again at that moment. The expiration date is not a covered day. The first run creates `data/clearance.db`. Tests set `CLEARANCE_DB` to a temporary file.

The desk flow is in [docs/architecture.md](docs/architecture.md). Coverage stays with the rules: [docs/decisions/001-rules-decide.md](docs/decisions/001-rules-decide.md). The one loop is [docs/decisions/002-one-loop.md](docs/decisions/002-one-loop.md). The database choice is [docs/decisions/003-sqlite.md](docs/decisions/003-sqlite.md). The fake model in CI is [docs/decisions/005-fake-model-in-ci.md](docs/decisions/005-fake-model-in-ci.md).

## Run

Python 3.12 or newer. From this folder, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:CLEARANCE_MODEL = "fake"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health). The body is `{"status": "ok"}`. Stop the server with Ctrl+C.

`CLEARANCE_MODEL=fake` plays a built-in demo script and does not call a model. `CLEARANCE_MODEL=live` calls `grok-4.7` and needs `XAI_API_KEY` in the environment. With neither the variable nor the key, `POST /cases/{id}/run` returns 400 and names `fake` and `live`.

## Marcus, on the fake model

The folder below is the golden file. `today` is 15 June 2026, so the memo is Northglass Auto at 738.00. Set `CLEARANCE_MODEL` to `fake` in the server process, then in another PowerShell window:

```powershell
$base = "http://127.0.0.1:8000"
$case = Invoke-RestMethod -Method Post -Uri "$base/cases"
$id = $case.id
$folder = @"
insured_name: Marcus Hale
license_number: S10000023
license_issued_on: 2014-03-01
license_expires_on: 2028-03-01
vin: 1FAKE0HALE0CAR001
plate: MA 4KTP92
vehicle_year: 2018
prior_policy_expires_on: 2027-03-01
sdip_points: 0
line_of_business: auto
"@
$document = @{ name = "folder.txt"; body_text = $folder } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/cases/$id/documents" -ContentType "application/json" -Body $document
Invoke-RestMethod -Method Post -Uri "$base/cases/$id/run?today=2026-06-15"
Invoke-RestMethod -Method Post -Uri "$base/cases/$id/bind?today=2026-06-15"
```

The bind response has `effective_on` 2026-06-15 and `expires_on` 2027-06-15. Coverage runs up to, and not including, the expiration date.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

GitHub Actions runs the same test on Ubuntu for every push and pull request. The job installs `requirements.txt` and runs `pytest`. The suite covers the health route, the case and document API, cited facts, the memo premium, the recommendation order, the Northglass premium of 738.00, the agent loop, and bind. The job has no API key and does not call xAI.
