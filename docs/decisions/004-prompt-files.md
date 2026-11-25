# ADR 004: The prompt is a file

## Context

The words sent to the model change what it cites and what memo it proposes. If those words live only inside a function, a stored memo cannot be tied back to the text that produced it.

Token use is part of the same record. A run that does not keep the count cannot be costed later.

## Decision

Prompt v1 is the file `app/agent/prompts/clearance-v1.md`. Each run stores `prompt_version` as `clearance-v1` and stores the model name, `fake` or `grok-4.7`.

A wording change is a new file and a new version string. The old file stays, so an old run still names the text that was sent.

When the provider reports usage, the model step stores `token_count` on its response. A turn with no count stores null. The premium on the memo still comes from `shop`.

## Consequence

`GET /runs/{id}` shows the prompt version, the model, and the token count on each model step that had one. CI uses `FakeLLM` and does not call xAI. A live count appears only after a real call.
