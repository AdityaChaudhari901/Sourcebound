# Staging Environment

## Purpose

Staging is a pre-production environment that mirrors production for final
verification before release.

## Deploys

Every merge to main auto-deploys to staging. Promotion from staging to production
is manual and requires approval.

## Data

Staging uses synthetic test data only. Real customer PII is never copied into
staging.
