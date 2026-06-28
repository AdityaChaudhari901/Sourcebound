# Observability

## Logging

All services emit structured JSON logs with a correlation id. Application logs are
retained for 30 days, after which they are deleted.

## Metrics

We track the four golden signals: latency, traffic, errors, and saturation. An
alert fires when p99 latency exceeds 300ms.

## Tracing

Distributed traces are sent to Langfuse. Production sampling is set to 10% of
requests to keep tracing cost down.

## Dashboards

Per-service dashboards live in Grafana and are linked from each service runbook.
