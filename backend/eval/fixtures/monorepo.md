# Monorepo

## Structure

All services live in a single monorepo under `services/`, with shared code in
`libs/`.

## Building

Run `make build` to build every service and `make test` to run the full test
suite locally.

## Branching

We practice trunk-based development: merge small changes to main behind feature
flags rather than maintaining long-lived branches.
