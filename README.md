# Bank Onboarding Flow

Sample Python web application for a configurable customer onboarding journey across Sweden, Spain and Poland for private and business customers.

## What is included

- Six configured journeys: Sweden, Spain and Poland for `private` and `business`.
- Server-rendered FastAPI/Jinja web flow with step validation and a progress indicator.
- SQLite persistence for applications, step responses, integration logs, request IDs and optimistic versions.
- Deterministic mocked checks for identity, address lookup, sanctions/PEP, registry, representative authority, UBO/KYB, credit and bank-account outcomes.
- A separate decisioning layer (`AutomatedDecisionEngine`) that maps integration signals to `APPROVED`, `MANUAL_REVIEW` or `REJECTED`, so the policy lives in one place rather than inside each mock.
- State transition checks prevent users from jumping ahead to later steps before prior steps are completed.
- Resume entry point for incomplete applications using an expiring HTTP-only resume cookie.
- Tests for flow registration, validation, decisioning and orchestration behavior.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

Alternatively:

```powershell
.\.venv\Scripts\python.exe run.py
```

Required local configuration lives in `.env`:

```env
DATABASE_URL=sqlite:///./onboarding.db
ONBOARDING_INTERNAL_SECRET=replace-this-local-development-secret
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Docker

Build and run with Docker Compose:

```powershell
docker compose up --build
```

Open `http://127.0.0.1:8000`.

The compose setup stores SQLite data in a named Docker volume and injects local development environment variables. It is useful for repeatable local runs, but it is not a production deployment design.

## Architecture

- `web/`: FastAPI routes, request parsing, validation orchestration and dependency wiring.
- `templates/`: Jinja pages for start, step, resume and decision screens.
- `flows/`: country and account-type flow configuration. Adding a new journey should mostly mean adding another `FlowConfig` and registering it.
- `domain/`: flow model, status model, the decisioning engine and ports.
- `services/`: onboarding and resume use cases, plus the `IntegrationRunner`.
- `integrations/`: deterministic mock external clients.
- `repositories/`: SQLAlchemy persistence implementation.
- `db/`: SQLite engine/session and ORM records.

Responsibilities are deliberately separated so each has one reason to change:

- `OnboardingService` orchestrates a step: guards state, persists, and sequences the checks.
- `IntegrationRunner` knows how to call each mock provider and fail safe.
- `AutomatedDecisionEngine` owns risk policy; provider authority checks return their own verdict (see ARCHITECTURE.md).

The web layer has no per-step controller branch; steps are driven by declarative `FlowConfig` definitions.

See [ARCHITECTURE.md](ARCHITECTURE.md) for a simple layer diagram and request flow.

## Data model

- `applications`: selected country/type, current status, optimistic version, request ID, resume handle, handle expiry and timestamps.
- `step_responses`: one saved response per application step, with a payload hash for idempotency.
- `integration_logs`: append-only audit-style record of mocked external checks, outcome, request ID and execution time.
- `decisions`: one row per application: the final `outcome` plus the structured `reasons` that drove it (e.g. `credit_bureau:REJECTED`). Reasons are for back office and audit only; the customer-facing decision page never shows them, just a generic status and a reference. Showing them would leak thresholds and risk tipping off.

### Handling sensitive data

Captured answers are stored as entered in `step_responses`. A bank legitimately needs to read these back (support, review, compliance), so redacting them into oblivion would be the wrong default; it destroys data the business owns. Protecting them is a storage concern: in production this means encryption at rest (e.g. KMS backed column/field encryption), tokenisation of the highest sensitivity identifiers, access control and a retention policy. This sample uses a local SQLite database and is explicitly not production secure storage.

What we do keep clean is the audit/operational trail. Provider responses written to `integration_logs` are redacted before storage. Redaction is key based (it masks the whole value with `[REDACTED]` regardless of type) and walks nested structures, so a sensitive value buried inside an object cannot leak. The key set is derived from the field catalog (`domain/fields.py`): every `FieldSpec` declares a `sensitive` clearance that defaults to `True`, so the design is secure by default, a field that forgets to declare itself is masked rather than leaked, and only fields explicitly cleared as non sensitive (e.g. `legal_form`, `sector`) pass through. The set is the catalog's sensitive fields plus two non field provider signal keys (`disposable_income`, `matched_country`); it stays narrow so innocent keys like `status` are not masked. Production would use path aware redaction.

Step idempotency uses a plain SHA-256 fingerprint of the submitted payload to detect an unchanged resubmission and skip re-running its checks. It is change detection, not a security signature, so it deliberately uses no HMAC or secret.

### External check failures

Integrations are async. Each call runs under a per attempt timeout (`asyncio.wait_for`) with a small retry loop; a configurable demo delay can simulate latency. A transient outage is treated as exactly that: the runner raises `IntegrationUnavailableError`, the step is not saved, and the web layer returns 503 asking the customer to retry. A network failure is never converted into a `MANUAL_REVIEW` outcome; doing so would flood back office queues with healthy applications during a provider blip. Timeouts, attempts and delay are in `config.Settings`. Backoff and a circuit breaker would be the next production step.

### Concurrency, transactions and configuration

A step submission writes the step response, integration logs, status update and decision inside a single unit of work (`repository.atomic()`): it commits once on success, or rolls back entirely on any error, so the database never holds partial state (ACID). Integrations run before the transaction opens, so the transaction stays short.

Concurrency is optimistic: the form posts the `version` it was rendered with, and the status update runs `UPDATE ... WHERE version=?`, so a stale tab or a tampered value returns 409 (rolling back the whole submission) rather than overwriting newer state. The posted value is only ever used inside that guard.

Decisioning thresholds (DTI, ownership concentration, high risk sectors) and integration timeouts live in `config.Settings` and are injected at startup, rather than hardcoded in the domain.

## Deterministic mock behavior

- Identity: values ending in `0000` reject, values ending in `1111` go to manual review, other valid formats approve.
- Sanctions/PEP: the screening mock reports sanctioned tax residencies and PEP status; the decision engine rejects a sanctions hit and refers a PEP match to manual review.
- Credit: the credit mock reports disposable income and leverage; the decision engine rejects negative disposable income and refers high debt-to-income to manual review.
- Registry: company identifiers starting with `00` reject; identifiers ending in `1111` go to manual review.
- Representative: missing signatory authority goes to manual review.
- UBO: missing UBO rejects; very concentrated ownership goes to manual review.
- Business credit: zero turnover rejects; high-risk sector or expected monthly volume above turnover goes to manual review.
- Bank account: IBANs ending in `9999` simulate a name mismatch and go to manual review; IBANs ending in `0000` simulate an unreachable provider (the call times out, is retried, then returns 503).

## Assumptions and tradeoffs

- Country rules are representative mocks, not legal/compliance claims.
- The UI intentionally stays simple; the focus is flow adaptability, validation, state and decisioning.
- Resume uses a high-entropy server-issued handle with expiry, stored in an HTTP-only cookie, and returns a generic error to avoid state disclosure. A production version would bind this to an authenticated customer session or deliver a magic link through a verified channel, with rate limiting and dedicated audit events.
- Audit logging is persisted in `integration_logs`; a production version would likely make audit writes more explicit, immutable and monitored.
- No real national eID, KYC, registry, credit bureau or banking API is called.

## Limitations

Known, deliberate boundaries of this sample:

- A `MANUAL_REVIEW` application is a final stop for the *customer*; there is no operator/back-office path to resolve it (would be a separate authenticated API).
- The flow stops at the first step that produces an adverse outcome. All checks *within that step* are run and all their reasons recorded, but checks in later steps are not reached, so the `reasons` reflect that step only.
- Stored application data is not encrypted at rest in this sample (documented above as a production concern, not implemented).
- Schema is created via `create_all()`; there are no migrations. A real deployment would use Alembic.
- No authentication/authorization, rate limiting or CSRF protection.
- Country-specific business rules are representative mocks; all markets share the same decisioning thresholds.
- A completed step cannot be re-submitted with different data (resume returns to the first *incomplete* step).

## Production thinking and future improvements

### Provider routing and country safety

The current sample uses simple integration names in each flow step, such as `identity`, `sanctions` and `credit_bureau`. That keeps the take-home small, but production provider routing should be stricter.

A production design would split this into:

- Flow config: the journey requires an identity check, credit check or registry check.
- Provider capabilities: each provider declares supported countries, customer types, purposes and check types.
- Country policy: each market defines the legally and operationally allowed providers, for example BankID and Freja ID for Sweden, DNIe/Clave-style checks for Spain.
- Startup validation: the application fails to start if any configured flow cannot resolve to an allowed provider.
- Runtime guards: providers reject requests for unsupported countries even if configuration is wrong.

This avoids a Swedish journey accidentally calling a Spanish provider. It also makes provider changes reviewable in code review and CI.

### Multiple providers

Adding Freja ID next to BankID should not require rewriting the Swedish flow. The flow should continue to request identity verification. A provider policy would decide whether BankID is primary, Freja ID is fallback, or the customer can choose between them. The same pattern applies to credit bureaus, registries and sanctions providers.

### Security

The sample has security-oriented basics: server-side validation, request IDs, PII kept out of the audit/log trail (deep-redacted), a single state-transition gate, transient-failure isolation and an HTTP-only resume cookie. It is not production-secure banking software.

Production hardening would include authentication, authorization, CSRF protection, rate limiting, encrypted sensitive fields, hashed resume handles, KMS-backed secrets, provider credential isolation, least-privilege IAM, network isolation, WAF rules, stricter session handling, and data retention/deletion controls.

### Audit and logging

The current logging is useful for observability and lightweight traceability. It is not a full regulated audit system.

Production audit should separate operational logs from append-only audit events. Audit events should include actor, event type, request/correlation ID, previous and new state, reason code, flow version, rule version, timestamp and redacted metadata. For stronger tamper resistance, audit records should be written to an immutable or append-only store, such as S3 Object Lock or a dedicated audit service.

### Service boundaries

`OnboardingService` is kept readable by pulling out the two responsibilities most likely to change independently:

- `IntegrationRunner` already owns provider resolution and external check execution.
- `AutomatedDecisionEngine` already owns mapping signals to approved/manual/rejected.

If the codebase grew further, the remaining concerns currently inside the service could be split the same way:

- `StepAccessPolicy`: step reachability and submittable-state checks.
- `StepResponseService`: redaction, hashing, idempotency and downstream invalidation.
- `ApplicationStateService`: state transitions and optimistic concurrency.
- `AuditService`: durable audit events.

The split is driven by reasons to change, not by adding layers for their own sake; the route layer stays thin and the workflow stays explicit in one use-case handler rather than spread across templates, routes and integration clients.

### Database model

The current schema is suitable for the assignment: applications, step responses and integration logs. Production would need more explicit history and governance:

- `application_events` for append-only state history.
- `decision_records` with rule version and reason codes.
- `provider_requests` and `provider_responses` for external check traceability.
- `manual_review_cases` for human review workflow.
- `flow_versions` for knowing which journey definition was used.
- `customer_consents` for regulatory proof.
- An outbox table for reliable event publishing.

Current-state tables are useful for fast reads; event/audit tables are needed to prove what happened.

### Repository abstraction

The repository interface separates application logic from SQLAlchemy persistence and keeps service tests simple. In a tiny app it is borderline extra code, but it has value here because onboarding state, step responses and audit-style records are central business operations. In a production codebase this abstraction should be kept only where it protects important business logic from persistence details.

### Form rendering

The step template renders fields from flow configuration, so adding select options or ordinary fields usually does not require changing HTML. Adding a new field type does require template support. A production version would likely use a richer form schema with labels, help text, validation hints, display conditions, masking rules and design-system components.

### AWS deployment

For this application, a pragmatic AWS deployment would be:

- CloudFront and AWS WAF at the edge if public-facing.
- Application Load Balancer.
- ECS Fargate tasks running the FastAPI container.
- RDS PostgreSQL instead of SQLite.
- Secrets Manager or SSM Parameter Store for secrets.
- KMS for encryption.
- CloudWatch and OpenTelemetry for logs, metrics and traces.
- SQS or EventBridge for asynchronous provider checks and domain events.
- Private subnets for application tasks and database.

Kubernetes is not necessary by default. EKS would make sense if the organization already has a mature Kubernetes platform. Kafka/MSK would only be justified for high-volume event streaming, replay-heavy workflows or existing platform standards. For most onboarding workflows, SQS/EventBridge plus an outbox pattern is a simpler first production choice.

For long-running or retry-heavy onboarding workflows, AWS Step Functions or Temporal could be considered. The decision should be based on operational complexity, workflow duration, retry requirements and team ownership, not on architecture fashion.

## Useful demo inputs

- Sweden private identity: `199001011234`
- Spain private identity: `12345678Z`
- Poland private identity: `90010112345`
- Phone: `+46701234567`
- Address: `Main Street 12`
- Approved financial profile: income `5000`, expenses `2000`, debts `500`
- Manual review financial profile: income `5000`, expenses `1000`, debts `4000`
- Rejected financial profile: income `1000`, expenses `1500`, debts `0`
