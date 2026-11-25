# Architecture

Clearance is the back end for the new-business desk of a personal-lines agency. The broker uploads the client folder. An agent reads the documents, records facts with citations, and proposes a memo. Python rules compute the recommendation and the premium. The tool stores the memo when it agrees with those rules. A person binds the policy. The rules run again at bind time, and only then does the book gain a policy.

Phase 4 code answers `GET /health`, stores cases and documents, and records cited facts. `build_memo` writes the memo from `recommend` and `shop`. The model protocol has a scripted fake and an xAI client for `grok-4.7`, built only when `XAI_API_KEY` is set. The agent loop and bind are the charter below.

```mermaid
flowchart TD
  folder[Client folder] --> api[FastAPI]
  api --> cases[Case service]
  cases --> docs[Documents in SQLite]
  api --> loop[Agent loop]
  loop --> tools[list read record evaluate submit]
  tools --> clearance[Clearance service]
  clearance --> rules[Python rules]
  clearance --> rating[Six fictional carriers]
  loop --> trace[Run steps]
  person[Person at the desk] --> bind[Bind]
  bind --> book[Policy book]
  rules --> book
```

## One case

1. `POST /cases` creates the case.
2. `POST /cases/{id}/documents` stores each text file.
3. `POST /cases/{id}/run` runs the loop.
4. The loop reads the documents, records cited facts, calls `evaluate`, and calls `submit_memo`.
5. `submit_memo` recomputes the rules. A memo that disagrees comes back as an error, and the loop continues, up to 8 steps.
6. `GET /cases/{id}` returns the facts, the conflicts, the memo, and the trace.
7. `POST /cases/{id}/bind` writes a policy when the stored memo is `quote` and the rules still agree.

The agent is a client of the clearance service. Tests call that service with no model. A real model call is a manual command.

## Recommendations

`recommend(facts, today)` is a pure function. The first match wins.

| Order | Recommendation | When |
|---|---|---|
| 1 | `out_of_scope` | At least one line is on file, none of those values is auto, and there is no VIN. A missing line stays on the auto desk. |
| 2 | `decline` | A license is present and `license_expires_on` is on or before today. |
| 3 | `incomplete` | The file is on the auto desk and a required field is missing: `insured_name`, `license_number`, `vin`, or both `license_issued_on` and `prior_policy_expires_on`, so years licensed cannot be estimated. A missing line stays on that desk. |
| 4 | `refer` | The same field is cited in two documents with different values, the prior policy has already expired, `sdip_points` is missing, or `sdip_points` is 4 or more. |
| 5 | `quote` | Everything else. |

A plate conflict with the same VIN can still be rated. The recommendation is `refer`.

`quote` needs at least one firm offer from the rater. The premium on the memo is the number the rater returns.

SDIP here is points inside the window, the same public simplification as Policy Desk. It is not the legal Massachusetts worksheet.
