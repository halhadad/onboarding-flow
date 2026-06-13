# Architecture

This project is a small server-rendered FastAPI application that models a configurable banking onboarding flow. It is intentionally local and deterministic: no real eID, KYC, registry, credit bureau or bank services are called.

## Goals

- Support six onboarding journeys: Sweden, Spain and Poland for private and business customers.
- Keep country/customer-type flow differences explicit and easy to test.
- Persist application state, step responses, integration outcomes and final status.
- Demonstrate production thinking around validation, redaction, request tracing, resumability and audit-style records.

## Layer Diagram

```mermaid
flowchart TD
    Browser[Browser]
    Templates[Jinja templates]
    Web[web/ FastAPI routes and middleware]
    Forms[web/forms.py validation]
    Service[services/ OnboardingService and ResumeService]
    Runner[services/ IntegrationRunner]
    Decision[domain/ AutomatedDecisionEngine]
    Flow[flows/ and domain/flow_registry.py]
    Domain[domain/ entities, states, ports]
    Integrations[integrations/ deterministic mock clients]
    Repo[repositories/ SQLAlchemy repository]
    DB[(SQLite database)]
    Logs[audit/log.py structured logs]

    Browser --> Templates
    Templates --> Web
    Web --> Forms
    Web --> Service
    Service --> Flow
    Service --> Domain
    Service --> Runner
    Runner --> Integrations
    Runner --> Decision
    Service --> Repo
    Repo --> DB
    Web --> Logs
    Service --> Logs
```

`OnboardingService` sequences a step. `IntegrationRunner` calls the mock providers and, for credit and sanctions, hands their raw signals to `AutomatedDecisionEngine`, which is the single place a decision (approve/refer/reject) is made.

## Request Flow

1. The customer selects country and account type.
2. The web route creates an application record and redirects to the first configured step.
3. Each step is rendered from `FlowConfig` and `FormFieldConfig`.
4. Submitted form data is validated server-side.
5. `OnboardingService` checks that the step is reachable and that the application is still open for customer input (`is_customer_submittable` — the same gate the web layer uses, so the two cannot drift).
6. The step response is redacted (driven by the flow schema) for storage and hashed with HMAC-SHA256 for idempotency/change detection.
7. The step's required checks are executed by `IntegrationRunner`; credit and sanctions signals are turned into a decision by `AutomatedDecisionEngine`.
8. Integration outcomes are persisted to `integration_logs`.
9. The application status moves to `IN_PROGRESS`, `APPROVED`, `MANUAL_REVIEW` or `REJECTED`.
10. A server-issued resume handle is stored in an HTTP-only cookie so `/resume` can return incomplete applications to the first incomplete step without showing the handle to the customer. A read-only `/review` screen summarises captured (redacted) data and remaining steps.

## Main Modules

- `web/`: HTTP routes, middleware, dependency wiring and form validation entry points.
- `templates/`: Server-rendered pages for start, step, resume and decision views.
- `flows/`: Declarative country and account-type journey definitions.
- `domain/`: Flow models, entity/status models, ports and the `AutomatedDecisionEngine`.
- `services/`: Application use cases (step submission, resumability) and the `IntegrationRunner`.
- `integrations/`: Deterministic mock clients for identity, sanctions, credit, registry and bank account checks. Credit and sanctions return raw signals; other checks return their own outcome.
- `repositories/`: SQLAlchemy implementation of the persistence port.
- `db/`: ORM records and database session setup.
- `audit/`: Structured logging helpers.

## Current Tradeoffs

Provider plumbing (`IntegrationRunner`) and decision policy (`AutomatedDecisionEngine`) are already separated from `OnboardingService`, which keeps the service focused on sequencing a step. The remaining concerns still inside the service are deliberately left together because the sample is small; in a larger system they would be split the same way, around reasons to change:

- `StepAccessPolicy` — step reachability and submittable-state checks.
- `StepResponseService` — redaction, hashing, idempotency.
- `ApplicationStateService` — state transitions and optimistic concurrency.
- `AuditService` — durable audit events.

That remaining grouping is a deliberate take-home simplification, not the final production boundary.

## Production Direction

For production, provider selection should not be raw strings inside flow configuration. A safer design would separate:

- Flow config: what the customer journey requires.
- Provider capabilities: which countries/customer types each provider supports.
- Country policy: which providers are legally and operationally allowed.
- Startup validation: fail boot if a flow cannot resolve to an allowed provider.
- Runtime guards: providers reject requests for unsupported countries even if configuration is wrong.

That prevents a Swedish flow from accidentally calling a Spanish identity provider, and makes changes reviewable in pull requests and CI.
