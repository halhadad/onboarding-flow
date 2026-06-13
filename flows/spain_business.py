from domain.flow import FlowConfig, FlowStep, FormFieldConfig
from domain.enums import AccountType, Country, IntegrationName, PiiCategory, Sector

spain_business_flow = FlowConfig(
    country=Country.SPAIN,
    account_type=AccountType.BUSINESS,
    steps=[
        FlowStep(
            step_id="business_identity",
            title="Company NIF and Legal Form",
            description="Enter company NIF, legal form and registered address.",
            fields=[
                FormFieldConfig("company_identifier", "text", True, pii_category=PiiCategory.COMPANY_ID),
                FormFieldConfig("legal_name", "text", True),
                FormFieldConfig("legal_form", "select", True, ["SL", "SA", "Autonomo"]),
                FormFieldConfig("address", "text", True, pii_category=PiiCategory.ADDRESS),
            ],
            required_integrations=[IntegrationName.REGISTRY],
        ),
        FlowStep(
            step_id="representative",
            title="Legal Representative",
            description="Verify representative identity and authority.",
            fields=[
                FormFieldConfig("representative_name", "text", True),
                FormFieldConfig("representative_id", "text", True, pii_category=PiiCategory.NATIONAL_ID),
                FormFieldConfig("has_signatory_authority", "boolean", True, requires_true=True),
            ],
            required_integrations=[IntegrationName.IDENTITY, IntegrationName.REPRESENTATIVE],
        ),
        FlowStep(
            step_id="beneficial_owners",
            title="Beneficial Ownership",
            description="Capture beneficial owners and ownership percentages.",
            fields=[
                FormFieldConfig("ubo_count", "number", True),
                FormFieldConfig("largest_ownership_percent", "number", True),
            ],
            required_integrations=[IntegrationName.UBO_KYC, IntegrationName.SANCTIONS],
        ),
        FlowStep(
            step_id="business_profile",
            title="KYB and Bank Account",
            description="Provide sector, turnover, tax details and expected usage.",
            fields=[
                FormFieldConfig("sector", "select", True, [s.value for s in Sector]),
                FormFieldConfig("annual_turnover", "number", True),
                FormFieldConfig("expected_monthly_volume", "number", True),
                FormFieldConfig("iban", "text", True, pii_category=PiiCategory.IBAN),
            ],
            required_integrations=[IntegrationName.BUSINESS_CREDIT, IntegrationName.BANK_ACCOUNT],
        ),
    ],
)
