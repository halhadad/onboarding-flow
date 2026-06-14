from domain.flow import FlowConfig, FlowStep, FormFieldConfig
from domain.enums import AccountType, Country, IntegrationName
from domain.fields import FieldId, LEGAL_FORMS_SPAIN

spain_business_flow = FlowConfig(
    country=Country.SPAIN,
    account_type=AccountType.BUSINESS,
    steps=[
        FlowStep(
            step_id="business_identity",
            title="Company NIF and Legal Form",
            description="Enter company NIF, legal form and registered address.",
            fields=[
                FormFieldConfig(FieldId.COMPANY_IDENTIFIER),
                FormFieldConfig(FieldId.LEGAL_NAME),
                FormFieldConfig(FieldId.LEGAL_FORM, options_override=LEGAL_FORMS_SPAIN),
                FormFieldConfig(FieldId.ADDRESS),
            ],
            required_integrations=[IntegrationName.REGISTRY],
        ),
        FlowStep(
            step_id="representative",
            title="Legal Representative",
            description="Verify representative identity and authority.",
            fields=[
                FormFieldConfig(FieldId.REPRESENTATIVE_NAME),
                FormFieldConfig(FieldId.REPRESENTATIVE_ID),
                FormFieldConfig(FieldId.HAS_SIGNATORY_AUTHORITY, requires_true=True),
            ],
            required_integrations=[IntegrationName.IDENTITY, IntegrationName.REPRESENTATIVE],
        ),
        FlowStep(
            step_id="beneficial_owners",
            title="Beneficial Ownership",
            description="Capture beneficial owners and ownership percentages.",
            fields=[
                FormFieldConfig(FieldId.UBO_COUNT),
                FormFieldConfig(FieldId.LARGEST_OWNERSHIP_PERCENT),
            ],
            required_integrations=[IntegrationName.UBO_KYC, IntegrationName.SANCTIONS],
        ),
        FlowStep(
            step_id="business_profile",
            title="KYB and Bank Account",
            description="Provide sector, turnover, tax details and expected usage.",
            fields=[
                FormFieldConfig(FieldId.SECTOR),
                FormFieldConfig(FieldId.ANNUAL_TURNOVER),
                FormFieldConfig(FieldId.EXPECTED_MONTHLY_VOLUME),
                FormFieldConfig(FieldId.IBAN),
            ],
            required_integrations=[IntegrationName.BUSINESS_CREDIT, IntegrationName.BANK_ACCOUNT],
        ),
        FlowStep(
            step_id="review_consent",
            title="Review and Confirm",
            description="Review your application and confirm your consent before we make a decision.",
            fields=[
                FormFieldConfig(FieldId.CONSENT, requires_true=True),
            ],
            required_integrations=[],
        ),
    ],
)
