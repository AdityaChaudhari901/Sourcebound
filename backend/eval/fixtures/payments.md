# Payments Service

The payments service handles charges and refunds for customer transactions.

## Local Setup

Clone the repo and run `make up` to start the dev stack. Set the `STRIPE_KEY`
environment variable in your `.env` file. The service listens on port 8080 by default.

## Rotating Secrets

To rotate a secret, use the Vault CLI: `vault rotate payments`. Secrets must be
rotated every 90 days per the security runbook. Each rotation is written to the audit trail.

## Refunds

Refunds can be issued within 60 days of the original charge. Any refund over $1000
requires manager approval before it is processed.
