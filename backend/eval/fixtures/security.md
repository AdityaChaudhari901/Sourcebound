# Security Policy

## Secret Management

All application secrets are stored in Vault. Company policy requires every secret
to be rotated at least every 90 days, regardless of which service owns it.

## Multi-Factor Authentication

MFA is mandatory for all access to production systems. SSO sessions expire after 8
hours of inactivity.

## Access Reviews

Access to production is reviewed quarterly, and any unused grant is revoked.

## Vulnerability Scanning

CI scans dependencies on every pull request and blocks the merge on any critical
CVE.
