from domain.flow import FlowConfig, FlowStep, FormFieldConfig
from domain.enums import AccountType, Country, IntegrationName
from domain.fields import FieldId

poland_individual_flow = FlowConfig(
    country=Country.POLAND,
    account_type=AccountType.PRIVATE,
    steps=[
        FlowStep(
            step_id="collect_identity",
            title="PESEL Verification",
            description="Enter your PESEL so we can run an eID-style identity mock.",
            fields=[
                FormFieldConfig(FieldId.PERSONAL_IDENTITY_NUMBER),
            ],
            required_integrations=[IntegrationName.IDENTITY],
        ),
        FlowStep(
            step_id="confirm_contact",
            title="Contact and Registered Address",
            description="Confirm your phone number and registered address.",
            fields=[
                FormFieldConfig(FieldId.ADDRESS),
                FormFieldConfig(FieldId.PHONE_NUMBER),
            ],
            required_integrations=[IntegrationName.ADDRESS_LOOKUP],
        ),
        FlowStep(
            step_id="regulatory_declarations",
            title="Regulatory Declarations",
            description="Confirm PEP status, sanctions declaration and tax residency.",
            fields=[
                FormFieldConfig(FieldId.IS_PEP),
                FormFieldConfig(FieldId.TAX_RESIDENCY),
            ],
            required_integrations=[IntegrationName.SANCTIONS],
        ),
        FlowStep(
            step_id="financial_profile",
            title="BIK-style Affordability",
            description="Provide income and affordability information for the credit mock.",
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
