"""British-adopted Eurocode identifiers used by the V1 bridge profile.

The internal package name remains ``eurocode`` because the calculation rules
are Eurocode rules. User-facing provenance identifies the British adoption
explicitly as BS EN. National Annex choices are separate project inputs and are
not encoded as hidden defaults here.
"""

BS_EN_1990 = "BS EN 1990:2002+A1:2005"
BS_EN_1991_2 = "BS EN 1991-2:2003"
BS_EN_1992_2 = "BS EN 1992-2:2005"

BS_EN_ACTIONS_BASIS = f"{BS_EN_1990} / {BS_EN_1991_2}"
BS_EN_CONCRETE_BRIDGE_BASIS = f"{BS_EN_ACTIONS_BASIS} / {BS_EN_1992_2}"

# These are companion UK National Annex identifiers, not automatic Nigerian
# defaults. They may be selected only when the project/authority adopts them.
UK_NA_BS_EN_1991_2 = "NA+A1:2020 to BS EN 1991-2:2003"
UK_NA_BS_EN_1992_2 = "NA to BS EN 1992-2:2005"
