from domain.flow import FlowConfig, FlowStep, FormFieldConfig
from domain.enums import AccountType, Country, IntegrationName, PiiCategory, Sector

sweden_business_flow = FlowConfig(
    country=Country.SWEDEN,
    account_type=AccountType.BUSINESS,
    steps=[
        FlowStep(
            step_id="business_identity",
            title="Company Details",
            description="Enter organisation number, legal name and legal form.",
            fields=[
                FormFieldConfig("company_identifier", "text", True, pii_category=PiiCategory.COMPANY_ID),
                FormFieldConfig("legal_name", "text", True),
                FormFieldConfig("legal_form", "select", True, ["AB", "HB", "Enskild firma"]),
            ],
            required_integrations=[IntegrationName.REGISTRY],
        ),
        FlowStep(
            step_id="representative",
            title="Authorised Representative",
            description="Confirm the representative and signatory authority.",
            fields=[
                FormFieldConfig("representative_name", "text", True),
                FormFieldConfig("representative_id", "text", True, pii_category=PiiCategory.NATIONAL_ID),
                FormFieldConfig("has_signatory_authority", "boolean", True, requires_true=True),
            ],
            required_integrations=[IntegrationName.REPRESENTATIVE],
        ),
        FlowStep(
            step_id="beneficial_owners",
            title="Beneficial Owners",
            description="Capture beneficial owner count and highest ownership percentage.",
            fields=[
                FormFieldConfig("ubo_count", "number", True),
                FormFieldConfig("largest_ownership_percent", "number", True),
            ],
            required_integrations=[IntegrationName.UBO_KYC, IntegrationName.SANCTIONS],
        ),
        FlowStep(
            step_id="business_profile",
            title="Business Activity",
            description="Provide business activity, turnover and expected usage.",
            fields=[
                FormFieldConfig("sector", "select", True, [s.value for s in Sector]),
                FormFieldConfig("annual_turnover", "number", True),
                FormFieldConfig("expected_monthly_volume", "number", True),
            ],
            required_integrations=[IntegrationName.BUSINESS_CREDIT],
        ),
    ],
)
