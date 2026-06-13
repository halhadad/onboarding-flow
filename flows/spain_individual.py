from domain.flow import FlowConfig, FlowStep, FormFieldConfig
from domain.enums import AccountType, Country, IntegrationName, PiiCategory
from domain.countries import TAX_RESIDENCY_OPTIONS

spain_individual_flow = FlowConfig(
    country=Country.SPAIN,
    account_type=AccountType.PRIVATE,
    steps=[
        FlowStep(
            step_id="collect_identity",
            title="DNI/NIE Verification",
            description="Enter your DNI or NIE so we can run a deterministic identity check.",
            fields=[
                FormFieldConfig("personal_identity_number", "text", True, pii_category=PiiCategory.NATIONAL_ID),
            ],
            required_integrations=[IntegrationName.IDENTITY],
        ),
        FlowStep(
            step_id="confirm_contact",
            title="Contact and Address",
            description="Confirm contact details, province and residential address.",
            fields=[
                FormFieldConfig("address", "text", True, pii_category=PiiCategory.ADDRESS),
                FormFieldConfig("province", "text", True),
                FormFieldConfig("phone_number", "text", True, pii_category=PiiCategory.PHONE),
            ],
            required_integrations=[IntegrationName.ADDRESS_LOOKUP],
        ),
        FlowStep(
            step_id="regulatory_declarations",
            title="Compliance Declarations",
            description="Confirm consent, PEP status, sanctions declaration and tax residency.",
            fields=[
                FormFieldConfig("is_pep", "boolean", True),
                FormFieldConfig("tax_residency", "select", True, TAX_RESIDENCY_OPTIONS),
            ],
            required_integrations=[IntegrationName.SANCTIONS],
        ),
        FlowStep(
            step_id="financial_profile",
            title="Affordability Profile",
            description="Provide income, housing costs and other debts for credit decisioning.",
            fields=[
                FormFieldConfig("monthly_income", "number", True),
                FormFieldConfig("monthly_expenses", "number", True),
                FormFieldConfig("outstanding_debts", "number", True),
            ],
            required_integrations=[IntegrationName.CREDIT_BUREAU],
        ),
    ],
)
