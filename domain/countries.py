"""Tax-residency country options.

Tax residency is a property of a *person*, not of the market they are onboarding
into, so it is a broad ISO-3166 list rather than the three operating markets.
The list deliberately includes a few sanctioned jurisdictions so the
sanctions/PEP reject path is actually reachable from the UI.
"""

# Sanctioned jurisdictions the screening provider treats as a confirmed hit.
SANCTIONED_RESIDENCIES = frozenset({"IR", "KP", "SY"})

# A representative subset of ISO 3166-1 alpha-2 codes. Not exhaustive — a
# production app would source the full list from a maintained reference dataset.
TAX_RESIDENCY_OPTIONS = (
    "AT", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "ES",
    "FI", "FR", "GB", "GR", "HR", "HU", "IE", "IS", "IT", "LT",
    "LU", "LV", "MT", "NL", "NO", "PL", "PT", "RO", "SE", "SI",
    "SK", "US", "CA", "AU",
    # Included so the sanctions reject path can be exercised:
    "IR", "KP", "SY",
)
