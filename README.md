# Bank Onboarding Flow

Sample Python web application/service for customer onboarding across Sweden, Spain and Poland for private and business customers.

## Run locally

**macOS / Linux**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

**Windows**
```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\uvicorn main:app --reload
```

Or on either platform: `python run.py` (after activating the venv).

Requires a `.env` in the project root:

```env
DATABASE_URL=sqlite:///./onboarding.db
ONBOARDING_INTERNAL_SECRET=replace-this-local-development-secret
```

## Tests

```bash
# macOS / Linux
python -m pytest -q

# Windows
.\.venv\Scripts\python -m pytest -q
```

## Architecture

```
web/          routes, form validation, dependency wiring
flows/        declarative FlowConfig per country + account type
domain/       flow model, state machine, decisioning engine, ports
services/     OnboardingService, IntegrationRunner, ResumeService
integrations/ deterministic mock providers
repositories/ SQLAlchemy persistence
db/           SQLite engine, ORM models
```

The key split: `OnboardingService` orchestrates a step (guards, sequences, persists). `IntegrationRunner` owns provider dispatch and timeout/retry. `AutomatedDecisionEngine` owns risk policy. Provider authority checks (identity, registry, bank account) return the external system's own verdict and are mapped directly; risk checks (credit, sanctions, UBO) return raw facts and the engine decides.

Adding a new market is mostly a new `FlowConfig` in `flows/` and a registry entry. No per-step controller branch in the web layer.

See [ARCHITECTURE.md](ARCHITECTURE.md) for a simple layer diagram and request flow.

## Data model

Four tables: `applications`, `step_responses`, `integration_logs`, `decisions`.

- Step responses store the raw submitted answers. The bank legitimately reads these back for support and compliance; the right protection is encryption at rest (KMS-backed column encryption in production), not redaction.
- Integration logs are redacted before write. Redaction is key-based and walks nested structures. The key set comes from `domain/fields.py` where every `FieldSpec` has `sensitive=True` by default, so a new field that forgets to declare itself is masked, not leaked.
- Decisions store structured reasons (e.g. `credit_bureau:REJECTED`) for back office only. The decision page shows a generic status and a short reference derived from the application ID.
- Step idempotency: SHA-256 of the submitted payload. Unchanged resubmit skips integrations entirely. Change detection, not a security signature.

SQLite runs with WAL and IMMEDIATE isolation. Every step submission is a single unit of work (`repository.atomic()`): integrations run first to keep the DB lock window short, then all writes commit together or roll back entirely. Concurrency is optimistic: the posted `version` feeds a `UPDATE ... WHERE version=?` guard. A stale or tampered value returns 409 and rolls back.

Schema is created via `create_all()`. A real deployment would use Alembic.

## Mock behavior

- Identity: ends in `0000` rejects, `1111` goes to manual review, other valid formats approve.
- Registry: starts with `00` rejects, ends in `1111` goes to manual review.
- Sanctions/PEP: sanctioned tax residency rejects, PEP match goes to manual review.
- Credit: negative disposable income rejects, high DTI goes to manual review.
- UBO: missing UBO rejects, concentrated ownership goes to manual review.
- Representative: missing signatory authority goes to manual review.
- Business credit: zero turnover rejects, high-risk sector or volume above turnover goes to manual review.
- Bank account: IBAN ending `9999` is a name mismatch (manual review); ending `0000` simulates an unreachable provider (times out, retried, then 503).

## Decisions and tradeoffs

- **Step responses are stored as entered, not redacted.** The bank reads them back for support and compliance, so the right control is encryption at rest in production, not masking. Only the audit trail (`integration_logs`) is redacted, key-based, since copies of that data leak into logs/tickets/monitoring more easily than the primary table.
- **Provider authority checks return their own verdict; risk checks go through the engine.**


## Production gaps

**Provider routing.** Each flow step currently names an integration directly (`identity`, `credit_bureau`). Production needs a provider capability map (supported countries, customer types, check types) and a per-market policy (e.g. BankID or Freja ID for Sweden). Startup should fail if a flow cannot resolve to an allowed provider. This prevents a Swedish journey accidentally routing to a Spanish provider.

**Security.** The sample has the basics: server-side validation, request IDs, PII out of the audit trail, a single state-gate, transient failure isolation, HTTP-only resume cookie. Missing for production: authentication, authorization, rate limiting, encrypted fields at rest, hashed resume handles, secrets managed outside the codebase.

**Audit.** Current integration logs are useful for traceability but are not an immutable audit record. Production should separate operational logs from append-only audit events (actor, event type, correlation ID, previous/new state, rule version, timestamp) written to a store that does not allow deletion.

**State history.** The schema tracks current state only. Production needs `application_events` for append-only history, `decision_records` with rule versions, and a `manual_review_cases` table for the operator workflow (no back-office path is implemented here).

**Integration retries.** Current retry is fixed-interval with no backoff or circuit breaker. Production would use exponential backoff with jitter and a circuit breaker to avoid hammering a struggling provider.

**Deployment.** The app is a standard ASGI container - run it on any container platform (e.g. ECS). SQLite becomes PostgreSQL. Secrets come from a secrets manager rather than a `.env` file. Structured logs go to a log aggregator. Slow or unreliable provider calls move to a background queue so user-facing requests are not blocked by provider latency.

## Known limitations

- `MANUAL_REVIEW` is terminal for the customer; there is no operator path to resolve it.
- Checks in later steps are not reached once an adverse outcome is found in an earlier step.
- Country business rules are representative mocks; all markets share the same decisioning thresholds.
- No migrations, no auth, no rate limiting.

## Resumable flow

Applications can be resumed across devices using a time-limited token stored in a signed HTTP-only cookie.

**To demo:**
1. Start any onboarding flow and complete one or two steps.
2. Copy the URL - note the `application_id` in the path.
3. Close the tab (or clear cookies to simulate a different device, then go to `/resume`).
4. The app reads the resume token from the cookie, finds the first incomplete step, and redirects directly to it.
5. Tokens expire after 7 days (`RESUME_TOKEN_TTL_SECONDS`). An expired or unknown token renders an error on `/resume` and clears the cookie.

The token is a 32-byte URL-safe random value (`secrets.token_urlsafe`). It is stored in the `applications` table alongside its expiry and is never reused. The cookie is `HttpOnly` and `SameSite=Lax`.

## Demo inputs

| Field | Value |
|---|---|
| Sweden identity | `199001011234` |
| Spain identity | `12345678Z` |
| Poland identity | `90010112345` |
| Phone | `+46701234567` |
| Address | `Main Street 12` |
| Approved financials | income `5000`, expenses `2000`, debts `500` |
| Manual review financials | income `5000`, expenses `1000`, debts `4000` |
| Rejected financials | income `1000`, expenses `1500`, debts `0` |
| Business company identifier, Sweden/Poland (approved) | `5560360793` |
| Business company identifier, Sweden/Poland (manual review) | ends in `1111`, e.g. `5560361111` |
| Business company identifier, Sweden/Poland (rejected) | starts with `00`, e.g. `0099887766` |
| Business company identifier, Spain (approved) | `B12345678` |
| Business company identifier, Spain (manual review) | ends in `1111`, e.g. `B99991111` |
| Business company identifier, Spain (rejected) | not reachable — Spain's NIF format requires a leading letter, so a valid identifier can never start with `00` |
| IBAN, Spain/Poland (approved) | `ES9121000418450200051332` |
| IBAN, Spain/Poland (manual review, name mismatch) | ends in `9999`, e.g. `ES9121000418450200059999` |
| IBAN, Spain/Poland (provider timeout, then 503) | ends in `0000`, e.g. `ES9121000418450200050000` |
| Approved business financials | turnover `100000`, monthly volume `2000`, sector `RETAIL` |
| Manual review business financials | monthly volume above turnover, or sector `FINANCIAL_SERVICES` |
| Rejected business financials | turnover `0` |

