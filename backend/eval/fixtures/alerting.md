# Alerting

## Channels

SEV1 incidents page the on-call engineer via PagerDuty. Lower-severity SEV3 alerts
are posted to the `#alerts` Slack channel.

## Thresholds

The alerting system pages on-call when the production error rate exceeds 1% over a
five-minute window.

## Quiet Hours

There are no quiet hours for SEV1 pages; they fire 24/7.
