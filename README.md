# Bank Onboarding Flow

Sample Python web application for a configurable customer onboarding journey across Sweden, Spain and Poland for private and business customers.

## What is included

- Six configured journeys: Sweden, Spain and Poland for `private` and `business`.
- Server-rendered FastAPI/Jinja web flow with step validation and a progress indicator.
- SQLite persistence for applications, step responses, integration logs, request IDs and optimistic versions.
- Deterministic mocked checks for identity, address lookup, sanctions/PEP, registry, representative authority, UBO/KYB, credit and bank-account outcomes.
- Decision outcomes: `APPROVED`, `MANUAL_REVIEW` and `REJECTED`.
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
- `domain/`: flow model, status model, decisioning rules and ports.
- `services/`: onboarding and resume use cases.
- `integrations/`: deterministic mock external clients.
- `repositories/`: SQLAlchemy persistence implementation.
- `db/`: SQLite engine/session and ORM records.

The main design choice is to keep the flow definitions declarative and keep orchestration in `OnboardingService`. The service still maps integration names to deterministic mock behavior, but the web layer no longer has a separate hard-coded controller branch for every step.

See [ARCHITECTURE.md](ARCHITECTURE.md) for a simple layer diagram and request flow.

## Data model

- `applications`: selected country/type, current status, optimistic version, request ID, resume handle, handle expiry and timestamps.
- `step_responses`: one saved response per application step, with a payload hash for idempotency.
- `integration_logs`: append-only audit-style record of mocked external checks, outcome, request ID and execution time.

Sensitive identifiers such as personal identity numbers, representative IDs, company identifiers and IBANs are redacted before being stored in step response JSON. The sample still uses a local SQLite database and is not intended as production secure storage.

Step response payload digests use HMAC-SHA256 with `ONBOARDING_INTERNAL_SECRET`. This avoids plain unsalted hashes of low-entropy identifiers and supports per-step change detection/idempotency. In production the secret should come from managed secret storage with rotation.

## Deterministic mock behavior

- Identity: values ending in `0000` reject, values ending in `1111` go to manual review, other valid formats approve.
- Sanctions/PEP: PEP declarations go to manual review; blocked tax residencies in the rule engine reject.
- Credit: negative disposable income rejects; high debt-to-income goes to manual review.
- Registry: company identifiers starting with `00` reject; identifiers ending in `1111` go to manual review.
- Representative: missing signatory authority goes to manual review.
- UBO: missing UBO rejects; very concentrated ownership goes to manual review.
- Business credit: zero turnover rejects; high-risk sector or expected monthly volume above turnover goes to manual review.
- Bank account: IBANs ending in `9999` simulate a name mismatch and go to manual review.

## Assumptions and tradeoffs

- Country rules are representative mocks, not legal/compliance claims.
- The UI intentionally stays simple; the focus is flow adaptability, validation, state and decisioning.
- Resume uses a high-entropy server-issued handle with expiry, stored in an HTTP-only cookie, and returns a generic error to avoid state disclosure. A production version would bind this to an authenticated customer session or deliver a magic link through a verified channel, with rate limiting and dedicated audit events.
- Audit logging is persisted in `integration_logs`; a production version would likely make audit writes more explicit, immutable and monitored.
- No real national eID, KYC, registry, credit bureau or banking API is called.

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

The sample has security-oriented basics: server-side validation, request IDs, redaction before storing form responses, HMAC payload hashes, terminal status protection and an HTTP-only resume cookie. It is not production-secure banking software.

Production hardening would include authentication, authorization, CSRF protection, rate limiting, encrypted sensitive fields, hashed resume handles, KMS-backed secrets, provider credential isolation, least-privilege IAM, network isolation, WAF rules, stricter session handling, and data retention/deletion controls.

### Audit and logging

The current logging is useful for observability and lightweight traceability. It is not a full regulated audit system.

Production audit should separate operational logs from append-only audit events. Audit events should include actor, event type, request/correlation ID, previous and new state, reason code, flow version, rule version, timestamp and redacted metadata. For stronger tamper resistance, audit records should be written to an immutable or append-only store, such as S3 Object Lock or a dedicated audit service.

### Service boundaries

`OnboardingService` is intentionally central in this sample so the workflow is easy to follow. If the codebase grew, it would be split around reasons to change:

- `SubmitStepHandler`: use-case orchestration.
- `FlowResolver`: country/type flow lookup.
- `StepAccessPolicy`: step reachability and terminal-state checks.
- `StepResponseService`: redaction, hashing, idempotency and downstream invalidation.
- `CheckOrchestrator`: provider resolution and external check execution.
- `DecisionService`: mapping results to approved/manual/rejected.
- `ApplicationStateService`: state transitions and optimistic concurrency.
- `AuditService`: durable audit events.

The route layer should stay thin, and the workflow should remain explicit in one use-case handler rather than being spread across templates, routes and integration clients.

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
