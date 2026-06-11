from domain.flow import FlowConfig, FlowStep, FormFieldConfig


poland_business_flow = FlowConfig(
    country="POLAND",
    account_type="business",
    steps=[
        FlowStep(
            step_id="business_identity",
            title="NIP / REGON / KRS Details",
            description="Enter company identifier, legal name and legal form.",
            fields=[
                FormFieldConfig("company_identifier", "text", True),
                FormFieldConfig("legal_name", "text", True),
                FormFieldConfig("legal_form", "select", True, ["Sp. z o.o.", "SA", "CEIDG"]),
            ],
            required_integrations=["registry"],
        ),
        FlowStep(
            step_id="representative",
            title="Authority to Act",
            description="Confirm board member or sole proprietor authority.",
            fields=[
                FormFieldConfig("representative_name", "text", True),
                FormFieldConfig("representative_id", "text", True),
                FormFieldConfig("has_signatory_authority", "boolean", True),
            ],
            required_integrations=["representative"],
        ),
        FlowStep(
            step_id="beneficial_owners",
            title="Beneficial Owners",
            description="Capture beneficial ownership and risk indicators.",
            fields=[
                FormFieldConfig("ubo_count", "number", True),
                FormFieldConfig("largest_ownership_percent", "number", True),
            ],
            required_integrations=["ubo_kyc", "sanctions"],
        ),
        FlowStep(
            step_id="business_profile",
            title="Business Credit and Account",
            description="Provide VAT/tax flags, business activity and expected usage.",
            fields=[
                FormFieldConfig("sector", "select", True, ["retail", "services", "manufacturing", "financial_services"]),
                FormFieldConfig("annual_turnover", "number", True),
                FormFieldConfig("expected_monthly_volume", "number", True),
                FormFieldConfig("iban", "text", True),
            ],
            required_integrations=["business_credit", "bank_account"],
        ),
    ],
)
