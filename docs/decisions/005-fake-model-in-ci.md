# ADR 005: CI uses a fake model

## Context

A clearance run will call a model that can read a folder and propose a memo. The suite has to prove that mechanism on every push. A live call needs a key, a network, and money, and the answer can change.

The model id has to be copied from the current docs. A guessed name would fail on the first real request.

## Decision

On 2026-11-25 the docs at https://docs.x.ai link to https://docs.x.ai/developers/models. That page says to use Grok 4.7 for chat and for code. The model page it links, https://docs.x.ai/developers/models/grok-4.7, lists the model name `grok-4.7`. That is the id the live client sends.

The live client is one httpx call to `POST https://api.x.ai/v1/responses`, with temperature 0. The quickstart also names the `openai` package and `xai-sdk`. Those pull in more than this phase needs. httpx is already installed.

`XaiClient` is constructed only when `XAI_API_KEY` is set. The tests ask for `fake`. `FakeLLM` returns a script of turns and then an empty turn. No test calls the live client.

## Consequence

`pytest` needs no key and no network. A live call is a manual choice. The loop that spends those turns is the next phase. CI does not prove that `grok-4.7` still answers; it proves the client is not required for the suite.
