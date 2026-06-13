from domain.flow import FlowConfig, FlowStep, FormFieldConfig
from domain.enums import AccountType, Country, IntegrationName, PiiCategory
from domain.countries import TAX_RESIDENCY_OPTIONS

poland_individual_flow = FlowConfig(
    country=Country.POLAND,
    account_type=AccountType.PRIVATE,
    steps=[
        FlowStep(
            step_id="collect_identity",
            title="PESEL Verification",
            description="Enter your PESEL so we can run an eID-style identity mock.",
            fields=[
                FormFieldConfig("personal_identity_number", "text", True, pii_category=PiiCategory.NATIONAL_ID),
            ],
            required_integrations=[IntegrationName.IDENTITY],
        ),
        FlowStep(
            step_id="confirm_contact",
            title="Contact and Registered Address",
            description="Confirm your phone number and registered address.",
            fields=[
                FormFieldConfig("address", "text", True, pii_category=PiiCategory.ADDRESS),
                FormFieldConfig("phone_number", "text", True, pii_category=PiiCategory.PHONE),
            ],
            required_integrations=[IntegrationName.ADDRESS_LOOKUP],
        ),
        FlowStep(
            step_id="regulatory_declarations",
            title="Regulatory Declarations",
            description="Confirm PEP status, sanctions declaration and tax residency.",
            fields=[
                FormFieldConfig("is_pep", "boolean", True),
                FormFieldConfig("tax_residency", "select", True, TAX_RESIDENCY_OPTIONS),
            ],
            required_integrations=[IntegrationName.SANCTIONS],
        ),
        FlowStep(
            step_id="financial_profile",
            title="BIK-style Affordability",
            description="Provide income and affordability information for the credit mock.",
            fields=[
                FormFieldConfig("monthly_income", "number", True),
                FormFieldConfig("monthly_expenses", "number", True),
                FormFieldConfig("outstanding_debts", "number", True),
            ],
            required_integrations=[IntegrationName.CREDIT_BUREAU],
        ),
    ],
)
