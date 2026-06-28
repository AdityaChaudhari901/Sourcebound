# Billing Service

The billing service manages customer subscriptions and invoices. It is separate
from the payments service, which handles one-off charges and refunds.

## Local Setup

Run `make billing-up` to start the billing stack. Set the `BILLING_DB_URL`
environment variable to point at the invoices database. The service listens on
port 9090 by default.

## Stripe Webhooks

Billing consumes Stripe webhook events for subscription lifecycle changes. Verify
each incoming event with the `BILLING_WEBHOOK_SECRET` signing secret before
processing it.

## Dunning

When an invoice payment fails, the dunning process retries the charge up to 3
times over 7 days before the subscription is suspended.
