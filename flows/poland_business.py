from domain.flow import FlowConfig, FlowStep, FormFieldConfig
from domain.enums import AccountType, Country, IntegrationName
from domain.fields import FieldId, LEGAL_FORMS_POLAND

poland_business_flow = FlowConfig(
    country=Country.POLAND,
    account_type=AccountType.BUSINESS,
    steps=[
        FlowStep(
            step_id="business_identity",
            title="NIP / REGON / KRS Details",
            description="Enter company identifier, legal name and legal form.",
            fields=[
                FormFieldConfig(FieldId.COMPANY_IDENTIFIER),
                FormFieldConfig(FieldId.LEGAL_NAME),
                FormFieldConfig(FieldId.LEGAL_FORM, options_override=LEGAL_FORMS_POLAND),
            ],
            required_integrations=[IntegrationName.REGISTRY],
        ),
        FlowStep(
            step_id="representative",
            title="Authority to Act",
            description="Confirm board member or sole proprietor authority.",
            fields=[
                FormFieldConfig(FieldId.REPRESENTATIVE_NAME),
                FormFieldConfig(FieldId.REPRESENTATIVE_ID),
                FormFieldConfig(FieldId.HAS_SIGNATORY_AUTHORITY, requires_true=True),
            ],
            required_integrations=[IntegrationName.REPRESENTATIVE],
        ),
        FlowStep(
            step_id="beneficial_owners",
            title="Beneficial Owners",
            description="Capture beneficial ownership and risk indicators.",
            fields=[
                FormFieldConfig(FieldId.UBO_COUNT),
                FormFieldConfig(FieldId.LARGEST_OWNERSHIP_PERCENT),
            ],
            required_integrations=[IntegrationName.UBO_KYC, IntegrationName.SANCTIONS],
        ),
        FlowStep(
            step_id="business_profile",
            title="Business Credit and Account",
            description="Provide VAT/tax flags, business activity and expected usage.",
            fields=[
                FormFieldConfig(FieldId.SECTOR),
                FormFieldConfig(FieldId.ANNUAL_TURNOVER),
                FormFieldConfig(FieldId.EXPECTED_MONTHLY_VOLUME),
                FormFieldConfig(FieldId.IBAN),
            ],
            required_integrations=[IntegrationName.BUSINESS_CREDIT, IntegrationName.BANK_ACCOUNT],
        ),
    ],
)
