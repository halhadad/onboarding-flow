# Ikano-style Onboarding Flow

Sample Python web application for a configurable customer onboarding journey across Sweden, Spain and Poland for private and business customers.

## What is included

- Six configured journeys: Sweden, Spain and Poland for `private` and `business`.
- Server-rendered FastAPI/Jinja web flow with step validation and a progress indicator.
- SQLite persistence for applications, step responses, integration logs, request IDs and optimistic versions.
- Deterministic mocked checks for identity, address lookup, sanctions/PEP, registry, representative authority, UBO/KYB, credit and bank-account outcomes.
- Decision outcomes: `APPROVED`, `MANUAL_REVIEW` and `REJECTED`.
- State transition checks prevent users from jumping ahead to later steps before prior steps are completed.
- Resume entry point for incomplete applications.
- Tests for flow registration, validation, decisioning and orchestration behavior.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

Required local configuration lives in `.env`:

```env
DATABASE_URL=sqlite:///./onboarding.db
ONBOARDING_INTERNAL_SECRET=replace-this-local-development-secret
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

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

## Data model

- `applications`: selected country/type, current status, optimistic version, request ID, resume token fields and timestamps.
- `step_responses`: one saved response per application step, with a payload hash for idempotency.
- `integration_logs`: append-only audit-style record of mocked external checks, outcome, request ID and execution time.

Sensitive identifiers such as personal identity numbers, representative IDs, company identifiers and IBANs are redacted before being stored in step response JSON. The sample still uses a local SQLite database and is not intended as production secure storage.

Step response payload digests use HMAC-SHA256 with `ONBOARDING_INTERNAL_SECRET`. This avoids plain unsalted hashes of low-entropy identifiers and supports per-step change detection/idempotency. In production the secret should come from managed secret storage with rotation.

## Deterministic mock behavior

- Identity: values containing `0000` reject, values containing `1111` go to manual review, other valid formats approve.
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
- Resume currently accepts the reference entered by the user and returns a generic error to avoid state disclosure. A production version should issue a separate high-entropy resume token or magic link with expiry, rate limiting and audit events.
- Audit logging is persisted in `integration_logs`; a production version would likely make audit writes more explicit, immutable and monitored.
- No real national eID, KYC, registry, credit bureau or banking API is called.

## Useful demo inputs

- Sweden private identity: `199001011234`
- Spain private identity: `12345678Z`
- Poland private identity: `90010112345`
- Phone: `+46701234567`
- Address: `Main Street 12`
- Approved financial profile: income `5000`, expenses `2000`, debts `500`
- Manual review financial profile: income `5000`, expenses `1000`, debts `4000`
- Rejected financial profile: income `1000`, expenses `1500`, debts `0`
