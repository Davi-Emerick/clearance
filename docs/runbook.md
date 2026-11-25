# Runbook

The people and the prices are fictional. Commands are from the project folder, in PowerShell.

## The run exhausted the budget

Look at the run first.

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/runs/RUN_ID"
```

`status` is `budget_exhausted`. There are 8 model steps. The last one did not end in an accepted `submit_memo`, so no new memo was stored.

Read the tool steps from the bottom. A `record_facts` or `submit_memo` response with `error` is the usual reason the loop kept going. The prompt version on that run is the file `app/agent/prompts/<prompt_version>.md`.

## The key is missing

`POST /cases/{id}/run` with no `CLEARANCE_MODEL` and no `XAI_API_KEY` returns 400. The message names `fake` and `live`.

`CLEARANCE_MODEL=fake` uses the built-in demo script and does not call xAI.

`CLEARANCE_MODEL=live` needs `XAI_API_KEY` in the server process. The model name stored on the run is `grok-4.7`.

## A citation was rejected, and the model tried again

Open the `record_facts` step. The response is `{"error": "..."}`. The quote was not a span of that document, or the value was not inside the quote, or the document is from another case. None of that batch was stored.

The loop sends the error back and continues. If the model repeats the same citation, the run ends `budget_exhausted`. Fix the span, then run the case again.

## Reread a run_id

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/runs/RUN_ID"
```

The row has `prompt_version`, `model`, and `status`. Each step has the request and the response. A model step response includes `token_count` when the provider sent one.

## Repeat the live evaluation

Structural mode does not call a model:

```powershell
.\.venv\Scripts\python.exe -m evals.run_eval
```

The live measurement is a separate command. Set `XAI_API_KEY` first.

```powershell
$env:XAI_API_KEY = "the key from the console"
.\.venv\Scripts\python.exe -m evals.run_eval --live
```

The score is written to `evals/reports/<date>-grok-4.7.json`. Copy that score into the README with the date and the model id. Do not type a score that is not in the file.

With no key, `--live` exits 2 and says the live evaluation was not run. It does not write a report.
