# Incident Response

## Severity Levels

A SEV1 is a full outage and is declared when the production error rate exceeds 5%.
A SEV2 is a major degradation affecting some users. A SEV3 is a minor issue with a
workaround.

## On-Call

The on-call engineer is paged through PagerDuty. If the page is not acknowledged
within 15 minutes, it escalates to the secondary on-call.

## Reporting

Report a production incident by posting in the `#incidents` Slack channel. Do not
use the #platform channel for incidents.

## Postmortems

Every SEV1 and SEV2 requires a blameless postmortem, published within 48 hours of
resolution.
