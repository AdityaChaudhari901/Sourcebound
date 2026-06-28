# Going to Production

A go/no-go checklist for running Sourcebound for real users. Split into **what the
code now does for you** and **what you (the operator) must still do** — the second
list is the part nothing in the repo can do on your behalf.

---

## 1. What the app now enforces (in code)

These shipped with the production-hardening change and are driven by config
(`backend/.env`, see `.env.example`):

- **Fail-fast on insecure config.** With `SOURCEBOUND_ENVIRONMENT=staging|production`
  the app **refuses to boot** if `JWT_SECRET` is the dev default, `CORS` is `*`, or
  `DATABASE_URL` still uses the `sourcebound:sourcebound` credentials.
  (`app/core/config.py::_validate_production_secrets`.)
- **Readiness vs. liveness.** `/health` = liveness (static). `/ready` = readiness —
  checks Postgres, Qdrant, and Redis and returns **503** if any is down, so the load
  balancer stops routing without restart-looping. Point your LB/k8s readiness probe
  at `/ready` and liveness at `/health`.
- **Rate limiting.** Per API-token / client-IP, Redis-backed, returns the standard
  `429` envelope with `Retry-After`. Tune `SOURCEBOUND_RATE_LIMIT_PER_MINUTE`.
  **Fails open** if Redis is down (never takes the API offline).
- **Security headers** on every response (HSTS over HTTPS, `X-Content-Type-Options`,
  `X-Frame-Options: DENY`, `Referrer-Policy`), plus optional **HTTPS redirect**
  (`SOURCEBOUND_FORCE_HTTPS`) and **host allow-list** (`SOURCEBOUND_TRUSTED_HOSTS`).
- **Dependency CVE scan in CI** (`pip-audit` + `npm audit`) — advisory today; flip
  `continue-on-error` off in `.github/workflows/ci.yml` to make it a hard gate once
  findings are triaged.
- Already in place from earlier work: structured JSON logs with a correlation id,
  the consistent error envelope, graceful shutdown (uvicorn drains on SIGTERM,
  Langfuse flushes, DB/Redis pools close), and a gated Alembic `migrate` job.

### Minimum production `.env`
```bash
SOURCEBOUND_ENVIRONMENT=production
JWT_SECRET=$(openssl rand -hex 32)
SOURCEBOUND_CORS_ORIGINS=https://app.yourdomain.com
SOURCEBOUND_TRUSTED_HOSTS=api.yourdomain.com
DATABASE_URL=postgresql+asyncpg://app:<strong-password>@<host>:5432/sourcebound
# plus your LLM provider creds (see CLAUDE.md §8)
```

---

## 2. What you must still do (infra / ops — not in the repo)

These are **blockers** the code cannot do for you:

1. **TLS.** Terminate HTTPS at a managed LB / reverse proxy (or set
   `SOURCEBOUND_FORCE_HTTPS=true` + `TRUSTED_HOSTS` if the app is edge-facing). The
   stack ships no TLS.
2. **Real secrets from a manager.** Put `JWT_SECRET`, DB password, LLM creds, and the
   Langfuse `NEXTAUTH_SECRET`/`SALT` (also `change-me` defaults) in a secret manager
   (GCP Secret Manager / Vault / SSM), injected at runtime — not in a committed file.
3. **Production Vertex auth.** Replace the personal-ADC mount in `docker-compose.yml`
   (`~/.config/gcloud`) with a dedicated **service account** (Workload Identity on
   GKE/Cloud Run, or a scoped key), least-privilege = `roles/aiplatform.user`.
4. **Cost guardrails.** Every query hits Vertex twice (embed + generate). Set a **GCP
   billing budget + alert** and Vertex quota limits so abuse can't run up the bill.
   The in-app rate limit is the first line; the budget alert is the backstop.
5. **Backups + tested restore.** Schedule Postgres (system of record) and Qdrant
   snapshots, and actually practice a restore. An untested backup is a hope.

### Strongly recommended before real traffic
- **Alerting on symptoms** — page on error rate / p99 latency / Vertex spend (Langfuse
  traces are wired; add the alerts).
- **Data-privacy decision** — `gemini-embedding-001` sends doc + query text to Google.
  For sensitive tenants, keep `SOURCEBOUND_EMBEDDING_PROVIDER=fastembed` (local BGE).
  See [ADR-0008](decisions.md).
- **Shorten the JWT** (`jwt_access_token_expire_minutes`, currently 12h) and confirm
  every route depends on `CurrentPrincipal` (default-closed tenant isolation).
- **Resource limits + scaling** — CPU/memory limits per container; scale the API and
  Celery worker horizontally; add a Celery/Flower monitor.
- **Image scanning** (e.g. Trivy) in CI in addition to the dependency audit.

---

## 3. Pre-launch smoke test

```bash
curl -fsS https://api.yourdomain.com/health   # 200, liveness
curl -fsS https://api.yourdomain.com/ready    # 200 only if PG+Qdrant+Redis are up
# headers present:
curl -sI https://api.yourdomain.com/health | grep -i strict-transport-security
# rate limit returns the 429 envelope under load (set a low limit to verify)
```
