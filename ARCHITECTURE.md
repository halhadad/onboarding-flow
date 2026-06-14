# Architecture

## Step submission flow

What happens on every POST to `/application/{id}/step/{step_id}`.

```mermaid
sequenceDiagram
    participant Browser
    participant Web as web/views.py
    participant SVC as OnboardingService
    participant IR as IntegrationRunner
    participant DE as AutomatedDecisionEngine
    participant REPO as Repository
    participant DB as SQLite

    Browser->>Web: POST form data + version
    Web->>Web: validate_step_payload()
    Web->>SVC: process_step_submission()

    SVC->>REPO: get_step_response() -- fingerprint check
    alt same payload hash
        SVC-->>Web: skip integrations, return current status
    end

    loop each required integration
        SVC->>IR: run(integration_name, form_data)
        IR->>IR: asyncio.wait_for(timeout) with retry
        alt risk check (credit / sanctions / UBO)
            IR->>DE: assess(raw_facts)
            DE-->>IR: CheckOutcome
        else authority check (identity / registry / bank account)
            IR->>IR: map typed status to CheckOutcome
        end
        IR-->>SVC: IntegrationResult
    end

    Note over SVC: collect all adverse reasons<br/>worst outcome wins

    SVC->>REPO: atomic() -- single transaction
    REPO->>DB: save step_response
    REPO->>DB: log integration_logs (redacted)
    REPO->>DB: update applications WHERE version=?
    Note over DB: rowcount=0 raises ConcurrentModificationError (409)
    REPO->>DB: upsert decisions (if terminal)
    DB-->>REPO: commit

    Web-->>Browser: redirect to next step or decision page
```

## Decisioning boundary

Two kinds of check, two owners:

- **Authority checks** (identity, registry, bank account): the provider's status is the verdict. The adapter maps its typed enum (`IdentityStatus`, `RegistryStatus`, `BankAccountStatus`) directly to `CheckOutcome`. We do not re-derive what the external authority already decided.
- **Risk policy checks** (credit, sanctions, UBO, business credit, representative): the provider returns raw facts (`CreditAssessment`, `SanctionsScreening`, etc.). `AutomatedDecisionEngine` maps them to approve/refer/reject. Policy lives in one place, thresholds come from `config.Settings`.

## Data model

```mermaid
erDiagram
    applications ||--o{ step_responses : has
    applications ||--o{ integration_logs : has
    applications ||--o| decisions : has

    applications {
        string id PK
        string country
        string account_type
        string status
        int version
        string resume_token
        datetime resume_token_expires_at
        string request_id
    }
    step_responses {
        string id PK
        string application_id FK
        string step_id
        text form_data_json
        string payload_hash
    }
    integration_logs {
        string id PK
        string application_id FK
        string service_name
        string status_outcome
        text raw_response_json
        string request_id
    }
    decisions {
        string id PK
        string application_id FK
        string outcome
        text reasons_json
    }
```

## Deliberate decisions

- **`AutomatedDecisionEngine` is in `domain/`.** It is pure business policy with no I/O, so it belongs in the domain, not services.
- **Decision reasons are never shown to the customer.** They are stored in `decisions` for back office only. Showing them would leak thresholds.
- **Optimistic concurrency, not pessimistic.** Holding a row lock while a human fills a form is impractical. The posted `version` feeds `UPDATE ... WHERE version=?`; a stale or tampered value returns 409 and rolls back. No silent overwrite is possible.
- **Integrations run before the transaction opens.** Keeps the DB lock window short. A provider failure before any write leaves nothing in a partial state.
- **Mocks are wired at the composition root**, not swapped by env config. Provider swapping is a production concern.
- **Templates rely on Jinja autoescaping.** No manual escaping added.
