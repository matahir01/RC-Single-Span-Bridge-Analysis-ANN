from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ConsequenceClass(str, Enum):
    CC1 = "CC1"
    CC2 = "CC2"
    CC3 = "CC3"


@dataclass(frozen=True)
class TargetReliability:
    consequence_class: ConsequenceClass
    reference_period_years: int
    beta: float
    source: str
    note: str


_BS_EN_1990_TARGETS = {
    1: {
        ConsequenceClass.CC1: 4.2,
        ConsequenceClass.CC2: 4.7,
        ConsequenceClass.CC3: 5.2,
    },
    50: {
        ConsequenceClass.CC1: 3.3,
        ConsequenceClass.CC2: 3.8,
        ConsequenceClass.CC3: 4.3,
    },
}


def bs_en_1990_target_reliability(
    consequence_class: ConsequenceClass | str,
    reference_period_years: int = 50,
) -> TargetReliability:
    """Return the EN 1990 reliability target used for thesis sensitivity studies.

    The values reproduce the JRC summary of EN 1990 Annex C targets for ULS.
    They are exposed as explicit research inputs, not silently assigned to a
    real bridge project. National Annex/project requirements can supersede them.
    """

    consequence = ConsequenceClass(consequence_class)
    try:
        beta = _BS_EN_1990_TARGETS[reference_period_years][consequence]
    except KeyError as exc:
        raise ValueError(
            "Only the source-tabulated 1-year and 50-year EN 1990 targets are "
            "available in this helper."
        ) from exc

    return TargetReliability(
        consequence_class=consequence,
        reference_period_years=reference_period_years,
        beta=beta,
        source=(
            "European Commission JRC, Reliability requirements / EN 1990 Annex C "
            "target reliability table"
        ),
        note=(
            "Research reference target only. Confirm the adopted National Annex, "
            "consequence class and reference period for any real project."
        ),
    )


def thesis_reference_targets() -> tuple[TargetReliability, ...]:
    """Return CC1/CC2/CC3 50-year targets for sensitivity reporting."""

    return tuple(bs_en_1990_target_reliability(item, 50) for item in ConsequenceClass)
