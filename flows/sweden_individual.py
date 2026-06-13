from domain.flow import FlowConfig, FlowStep, FormFieldConfig
from domain.enums import AccountType, Country, IntegrationName, PiiCategory
from domain.countries import TAX_RESIDENCY_OPTIONS

sweden_individual_flow = FlowConfig(
    country=Country.SWEDEN,
    account_type=AccountType.PRIVATE,
    steps=[
        FlowStep(
            step_id="collect_identity",
            title="Identity Verification",
            description="Please enter your Swedish personal identity number to initiate verification via BankID.",
            fields=[
                FormFieldConfig("personal_identity_number", "text", True, pii_category=PiiCategory.NATIONAL_ID),
            ],
            required_integrations=[IntegrationName.IDENTITY],
        ),
        FlowStep(
            step_id="confirm_contact",
            title="Contact Details",
            description="Verify your current residential address and telephone information.",
            fields=[
                FormFieldConfig("address", "text", True, pii_category=PiiCategory.ADDRESS),
                FormFieldConfig("phone_number", "text", True, pii_category=PiiCategory.PHONE),
            ],
            required_integrations=[IntegrationName.ADDRESS_LOOKUP],
        ),
        FlowStep(
            step_id="regulatory_declarations",
            title="Regulatory Declarations",
            description="Provide necessary compliance, tax residency, and Politically Exposed Person status declarations.",
            fields=[
                FormFieldConfig("is_pep", "boolean", True),
                FormFieldConfig("tax_residency", "select", True, TAX_RESIDENCY_OPTIONS),
            ],
            required_integrations=[IntegrationName.SANCTIONS],
        ),
        FlowStep(
            step_id="financial_profile",
            title="Financial Profile",
            description="Please provide details regarding your monthly employment income, expenses, and outstanding liabilities.",
            fields=[
                FormFieldConfig("monthly_income", "number", True),
                FormFieldConfig("monthly_expenses", "number", True),
                FormFieldConfig("outstanding_debts", "number", True),
            ],
            required_integrations=[IntegrationName.CREDIT_BUREAU],
        ),
    ],
)
