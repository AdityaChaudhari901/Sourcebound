# Engineering Onboarding

Welcome to the platform engineering team.

## Getting Access

To set up the payments service locally, clone the monorepo and run `make up`.
Secrets are managed in Vault; request access by posting in the `#platform` Slack channel.
New hires are granted read-only access for the first two weeks.

## Code Review

Every pull request requires at least two approvals before it can be merged. The eval
harness runs in CI and blocks the merge if answer faithfulness drops below 0.8.
