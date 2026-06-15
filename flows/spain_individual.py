from domain.flow import FlowConfig, FlowStep, FormFieldConfig
from domain.enums import AccountType, Country, IntegrationName
from domain.fields import FieldId

spain_individual_flow = FlowConfig(
    country=Country.SPAIN,
    account_type=AccountType.PRIVATE,
    steps=[
        FlowStep(
            step_id="collect_identity",
            title="DNI/NIE Verification",
            description="Enter your DNI or NIE so we can run a deterministic identity check.",
            fields=[
                FormFieldConfig(FieldId.PERSONAL_IDENTITY_NUMBER),
            ],
            required_integrations=[IntegrationName.IDENTITY],
        ),
        FlowStep(
            step_id="confirm_contact",
            title="Contact and Address",
            description="Confirm contact details, province and residential address.",
            fields=[
                FormFieldConfig(FieldId.ADDRESS),
                FormFieldConfig(FieldId.PROVINCE),
                FormFieldConfig(FieldId.PHONE_NUMBER),
            ],
            required_integrations=[IntegrationName.ADDRESS_LOOKUP],
        ),
        FlowStep(
            step_id="regulatory_declarations",
            title="Compliance Declarations",
            description="Confirm consent, PEP status, sanctions declaration and tax residency.",
            fields=[
                FormFieldConfig(FieldId.IS_PEP),
                FormFieldConfig(FieldId.TAX_RESIDENCY),
            ],
            required_integrations=[IntegrationName.SANCTIONS],
        ),
        FlowStep(
            step_id="financial_profile",
            title="Affordability Profile",
            description="Provide income, housing costs and other debts for credit decisioning.",
            fields=[
                FormFieldConfig(FieldId.MONTHLY_INCOME),
                FormFieldConfig(FieldId.MONTHLY_EXPENSES),
                FormFieldConfig(FieldId.OUTSTANDING_DEBTS),
            ],
            required_integrations=[IntegrationName.CREDIT_BUREAU],
        ),
        FlowStep(
            step_id="review_consent",
            title="Review and Confirm",
            description="Review your application and confirm your consent before we make a decision.",
            fields=[
                FormFieldConfig(FieldId.CONSENT, requires_true=True),
            ],
            required_integrations=[],
            is_review_step=True,
        ),
    ],
)
