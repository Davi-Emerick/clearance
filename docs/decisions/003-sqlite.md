# ADR 003: One SQLite file

## Context

The demo and the test suite need a place to store a case and its documents. A server database would need its own process, a port, and a setup step before `pytest`.

This version runs as one process. The broker opens the desk, uploads a folder, and reads the memo on the same machine.

## Decision

The portfolio version uses one SQLite file, `data/clearance.db`. The application creates the file and the tables on startup. The schema is `app/schema.sql`, applied with `CREATE TABLE IF NOT EXISTS`. Foreign keys are on. There is no migration tool.

Tests set `CLEARANCE_DB` to a temporary file. The suite does not write the demo database.

Postgres would belong to a version that runs more than one process.

## Consequence

`pytest` and the demo each start with one command. A document cannot point at a case that is not in the file. The schema is the whole data model, including tables the later phases fill in. This phase writes cases and documents only.
