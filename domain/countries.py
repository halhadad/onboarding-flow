# Tax residency is a person attribute, not a market; broad list, not the three markets.

# Jurisdictions the screening provider treats as a confirmed hit.
SANCTIONED_RESIDENCIES = frozenset({"IR", "KP", "SY"})

# Representative subset of ISO two letter country codes; sanctioned ones included so the reject path is reachable.
TAX_RESIDENCY_OPTIONS = (
    "AT", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "ES",
    "FI", "FR", "GB", "GR", "HR", "HU", "IE", "IS", "IT", "LT",
    "LU", "LV", "MT", "NL", "NO", "PL", "PT", "RO", "SE", "SI",
    "SK", "US", "CA", "AU",
    # Included so the sanctions reject path can be exercised:
    "IR", "KP", "SY",
)
