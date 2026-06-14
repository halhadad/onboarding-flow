from domain.flow import FlowConfig, FlowStep, FormFieldConfig
from domain.enums import AccountType, Country, IntegrationName
from domain.fields import FieldId

sweden_individual_flow = FlowConfig(
    country=Country.SWEDEN,
    account_type=AccountType.PRIVATE,
    steps=[
        FlowStep(
            step_id="collect_identity",
            title="Identity Verification",
            description="Please enter your Swedish personal identity number to initiate verification via BankID.",
            fields=[
                FormFieldConfig(FieldId.PERSONAL_IDENTITY_NUMBER),
            ],
            required_integrations=[IntegrationName.IDENTITY],
        ),
        FlowStep(
            step_id="confirm_contact",
            title="Contact Details",
            description="Verify your current residential address and telephone information.",
            fields=[
                FormFieldConfig(FieldId.ADDRESS),
                FormFieldConfig(FieldId.PHONE_NUMBER),
            ],
            required_integrations=[IntegrationName.ADDRESS_LOOKUP],
        ),
        FlowStep(
            step_id="regulatory_declarations",
            title="Regulatory Declarations",
            description="Provide necessary compliance, tax residency, and Politically Exposed Person status declarations.",
            fields=[
                FormFieldConfig(FieldId.IS_PEP),
                FormFieldConfig(FieldId.TAX_RESIDENCY),
            ],
            required_integrations=[IntegrationName.SANCTIONS],
        ),
        FlowStep(
            step_id="financial_profile",
            title="Financial Profile",
            description="Please provide details regarding your monthly employment income, expenses, and outstanding liabilities.",
            fields=[
                FormFieldConfig(FieldId.MONTHLY_INCOME),
                FormFieldConfig(FieldId.MONTHLY_EXPENSES),
                FormFieldConfig(FieldId.OUTSTANDING_DEBTS),
            ],
            required_integrations=[IntegrationName.CREDIT_BUREAU],
        ),
    ],
)
