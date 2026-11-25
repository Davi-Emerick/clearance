# ADR 001: The model does not decide coverage

## Context

A new-business folder arrives as loose text. A model can miss a date, invent a premium, or follow a sentence inside a document that says to ignore the rules.

The recommendation and the price have to be the same on every run. A person at the desk has to be able to explain both.

## Decision

Python rules compute the recommendation and the premium. The model reads the documents, records facts with citations, and proposes a memo. The tool stores that memo only when the recommendation matches the rules. The model has no bind tool. A person binds the policy, and the rules run again before a row is written to `policies`.

## Consequence

A memo that disagrees with the rules is not stored. The premium on a stored memo is the rater's number. Tests can run the rules with no model and no network. Text inside a document does not change the recommendation or the price.
