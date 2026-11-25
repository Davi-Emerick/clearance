# Clearance desk — operator form

This file is the contract for one more phase. The application already runs. The page at `/` already opens three sample folders. This phase makes that same page usable by a person who will not open PowerShell and will not know the field names.

Read this file, execute Phase 11 only, and stop.

Do not import code from `C:\Users\Emerick\Desktop\Projects\apolices`. Do not add React, a build step, or a new dependency. Do not change `recommend`, `shop`, bind, or the agent loop. Do not call xAI. Do not run `--live`.

## What the person does

1. Starts the desk with the command already in the README. `CLEARANCE_MODEL` stays `fake`.
2. Opens `http://127.0.0.1:8000/`.
3. Types the file into a form, or presses one of the three sample buttons.
4. Presses Read this folder.
5. Reads one sentence that says quote, refer, decline, incomplete, or out of scope, in plain English, with the carrier and premium when there is one.
6. Presses Bind only when the sentence says the file can be quoted. Otherwise Bind stays disabled.
7. Can open the trace underneath. The trace is not the first thing on the page.

The desk date stays 15 June 2026. The page says that in the form, because a license date only makes sense against that clock.

## The form

Keep `static/index.html`, `static/desk.js`, and `static/styles.css`. One column. Same paper look. No animation. No front-end library.

Fields, in this order. Empty fields are left out of the document. The labels are human. The stored names are the fact names the desk already uses.

| Label on the page | Fact name |
|---|---|
| Insured name | `insured_name` |
| License number | `license_number` |
| License issued | `license_issued_on` |
| License expires | `license_expires_on` |
| VIN | `vin` |
| Plate | `plate` |
| Vehicle year | `vehicle_year` |
| Prior policy expires | `prior_policy_expires_on` |
| SDIP points | `sdip_points` |
| Line of business | `line_of_business` |

Line of business is a select with `auto`, `homeowners`, and `life`. It starts on `auto`.

Dates are typed as `YYYY-MM-DD`. The page does not invent a date picker library. A short hint under the date fields says `YYYY-MM-DD`.

An optional Note box is a second document, `note.txt`, only when the person typed something. The form itself becomes one document named `application.txt`. Each filled field is one line:

```text
insured_name: Marcus Hale
vin: 1FAKE0HALE0CAR001
```

Read this folder does the calls the sample buttons already do:

1. `POST /cases`
2. `POST /cases/{id}/documents` with `application.txt`
3. The note document, when there is one
4. `POST /cases/{id}/run?today=2026-06-15`
5. `GET /cases/{id}` and `GET /runs/{id}`

No new route. The fake script already reads `name: value` lines.

## The sentence

Replace the raw `quote · 738.00` line with a sentence a person can read. Keep the carrier and the premium in that sentence when the memo has them.

| Memo | Sentence |
|---|---|
| `quote` | This file can be quoted. {carrier} at {premium}. You can bind it. |
| `refer` | A person has to look at this file before anyone binds it. |
| `decline` | Do not bind this file. |
| `incomplete` | The folder is not complete. |
| `out_of_scope` | This is not an auto file. |

Under the sentence, list `reasons` and `missing` in the words the API already returns. Do not invent new reasons in JavaScript.

Bind is enabled only when `recommendation` is `quote`. Close stays available after a run. If bind returns 400, the banner shows `detail` from the API.

The three sample buttons stay and still load Marcus, Helen, and the injection note. After a sample run, the same sentence and the same Bind rule apply.

## README

Add a short "Use the desk" section above the Marcus PowerShell block:

- One command starts the server with `CLEARANCE_MODEL=fake`.
- Open `http://127.0.0.1:8000/`.
- Type a file, or press Marcus Hale.
- The premium is fictional. The desk date is 15 June 2026.

Do not bring back a `Status:` line. Do not claim a live score.

## Tests

Extend `tests/test_desk.py`. The suite still uses `CLEARANCE_MODEL=fake` and must not call the network.

- The page HTML contains the form labels, Read this folder, and the three sample buttons.
- Building the Marcus fields into `application.txt`, posting it, and running the case returns `quote`, Northglass Auto, and `738.00`. Bind then succeeds.
- The same path with `license_expires_on` of `2024-01-01` returns `decline`. Bind returns 400 and writes no policy.
- `desk.js` contains the five sentences above.
- The sample-folder test already in this file still passes.

## Done when

`pytest` passes. The form and the three sample buttons share one result area. Bind is off unless the memo is `quote`.

Do not mark Phase 11 in `PLAN.md`. This phase lives only in this file. Check the box below when the tests pass.

- [x] Phase 11 — Operator form

## Owner questions

- What does the person type, and what does the page send to the API?
- When is Bind disabled?
- Why does this page still not call Grok?
