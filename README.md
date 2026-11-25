# Clearance

Clearance reads a new-business folder and writes a short memo: quote, refer, decline, incomplete, or out of scope. The premium and the recommendation come from Python rules. The model supplies cited facts and a memo that has to agree with those rules. A person binds the policy.

The people, the documents, and the carrier prices are fictional. Nothing in this repository is a real book of business, a government ID, or a filed rate.

SDIP in this project is points inside the window, not the legal Massachusetts worksheet.

Status: phase 4

This checkout answers `GET /health`, stores a case and its text documents, and accepts a cited fact set with no API key. `build_memo` is the only writer of a memo. The premium on that memo comes from `shop`. A live model call uses `grok-4.7` when `XAI_API_KEY` is set. The tests use a fake model. The first run creates `data/clearance.db`. Tests set `CLEARANCE_DB` to a temporary file.

The desk flow is in [docs/architecture.md](docs/architecture.md). Coverage stays with the rules: [docs/decisions/001-rules-decide.md](docs/decisions/001-rules-decide.md). The database choice is [docs/decisions/003-sqlite.md](docs/decisions/003-sqlite.md). The fake model in CI is [docs/decisions/005-fake-model-in-ci.md](docs/decisions/005-fake-model-in-ci.md).

## Run

Python 3.12 or newer. From this folder, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health). The body is `{"status": "ok"}`. Stop the server with Ctrl+C.

`.env.example` names `XAI_API_KEY`. This checkout does not read that variable.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

GitHub Actions runs the same test on Ubuntu for every push and pull request. The job installs `requirements.txt` and runs `pytest`. The suite covers the health route, the case and document API, cited facts, the memo premium, the recommendation order, the Northglass premium of 738.00, and a scripted fake model. The job has no API key and does not call xAI.
