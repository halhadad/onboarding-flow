from domain.flow import FlowConfig, FlowStep, FormFieldConfig
from domain.enums import AccountType, Country, IntegrationName
from domain.fields import FieldId, LEGAL_FORMS_SWEDEN

sweden_business_flow = FlowConfig(
    country=Country.SWEDEN,
    account_type=AccountType.BUSINESS,
    steps=[
        FlowStep(
            step_id="business_identity",
            title="Company Details",
            description="Enter organisation number, legal name and legal form.",
            fields=[
                FormFieldConfig(FieldId.COMPANY_IDENTIFIER),
                FormFieldConfig(FieldId.LEGAL_NAME),
                FormFieldConfig(FieldId.LEGAL_FORM, options_override=LEGAL_FORMS_SWEDEN),
            ],
            required_integrations=[IntegrationName.REGISTRY],
        ),
        FlowStep(
            step_id="representative",
            title="Authorised Representative",
            description="Confirm the representative and signatory authority.",
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
            description="Capture beneficial owner count and highest ownership percentage.",
            fields=[
                FormFieldConfig(FieldId.UBO_COUNT),
                FormFieldConfig(FieldId.LARGEST_OWNERSHIP_PERCENT),
            ],
            required_integrations=[IntegrationName.UBO_KYC, IntegrationName.SANCTIONS],
        ),
        FlowStep(
            step_id="business_profile",
            title="Business Activity",
            description="Provide business activity, turnover and expected usage.",
            fields=[
                FormFieldConfig(FieldId.SECTOR),
                FormFieldConfig(FieldId.ANNUAL_TURNOVER),
                FormFieldConfig(FieldId.EXPECTED_MONTHLY_VOLUME),
            ],
            required_integrations=[IntegrationName.BUSINESS_CREDIT],
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
