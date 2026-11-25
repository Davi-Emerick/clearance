# Clearance

Clearance reads a new-business folder and writes a short memo: quote, refer, decline, incomplete, or out of scope. The premium and the recommendation come from Python rules. The model supplies cited facts and a memo that has to agree with those rules. A person binds the policy.

The people, the documents, and the carrier prices are fictional. Nothing in this repository is a real book of business, a government ID, or a filed rate.

SDIP in this project is points inside the window, not the legal Massachusetts worksheet.

Status: phase 1

This checkout answers `GET /health` and rates a structured auto file. `recommend` chooses quote, refer, decline, incomplete, or out of scope. `shop` prices six fictional carriers. The case API and the agent are described in [docs/architecture.md](docs/architecture.md). The decision that the model does not decide coverage is [docs/decisions/001-rules-decide.md](docs/decisions/001-rules-decide.md).

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

GitHub Actions runs the same test on Ubuntu for every push and pull request. The job installs `requirements.txt` and runs `pytest`. The suite covers the health route, the recommendation order, and the Northglass premium of 738.00. The job has no API key and makes no model call.
