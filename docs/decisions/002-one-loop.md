# ADR 002: One hand-written loop

## Context

The clearance desk needs a model to read a folder, cite facts, and propose a memo. A framework would hide the step where a tool result goes back to the model. In an interview that step has to be drawn on a board.

The rules already decide the recommendation and the premium. The loop only carries messages and tool results.

## Decision

One function, `run_case`, calls the model at most 8 times. The tools are `list_documents`, `read_document`, `record_facts`, `evaluate`, and `submit_memo`. There is no bind tool and no agent framework.

`record_facts` on this path reuses the citation checks and writes the facts on the agent run. It does not open the manual run used by `POST /cases/{id}/facts`. `evaluate` returns the legal recommendation and the offers and does not store a memo. `submit_memo` stores a memo only when the recommendation matches that result, and only through `build_memo`. The stored carrier and premium come from `shop`. A number the model sends is kept in the step request and is not the stored premium.

A tool error is JSON `{"error": "..."}` and the loop continues. An unexpected exception marks the run `failed`. At step 8 with no accepted memo, the run is `budget_exhausted` and no new memo is stored.

## Consequence

The trace in `steps` is the whole story of a run: each model response and each tool call. A test can inject `FakeLLM` and never call xAI. The live client still sends `store: false` and replays the previous response output, including reasoning items, because those responses are not kept on the server.
