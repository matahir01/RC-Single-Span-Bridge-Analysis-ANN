from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ResearchEvidenceState(str, Enum):
    NOT_STARTED = "not_started"
    IMPLEMENTED = "implemented"
    VALIDATED = "validated"
    ACCEPTED = "accepted"


@dataclass(frozen=True)
class ResearchAcceptanceItem:
    key: str
    title: str
    state: ResearchEvidenceState
    evidence: str
    remaining: str

    @property
    def accepted(self) -> bool:
        return self.state is ResearchEvidenceState.ACCEPTED


@dataclass(frozen=True)
class ResearchAcceptanceGate:
    items: tuple[ResearchAcceptanceItem, ...]

    @property
    def accepted(self) -> bool:
        return bool(self.items) and all(item.accepted for item in self.items)

    @property
    def blockers(self) -> tuple[str, ...]:
        return tuple(item.key for item in self.items if not item.accepted)


def ann_reliability_rbdo_gate() -> ResearchAcceptanceGate:
    """Current evidence gate for the thesis research layer.

    This gate is intentionally distinct from the deterministic-engine release
    gates. Having executable sampling/ANN/FORM/RBDO code is not equivalent to
    having accepted probabilistic assumptions or validated research results.
    """

    return ResearchAcceptanceGate(
        items=(
            ResearchAcceptanceItem(
                key="probabilistic_model",
                title="Source-justified probabilistic model",
                state=ResearchEvidenceState.IMPLEMENTED,
                evidence=(
                    "Normal, lognormal and uniform random variables, truncation, LHS and "
                    "independent standard-normal transforms are implemented and tested."
                ),
                remaining=(
                    "Adopt and cite the final distributions, means/biases, COVs, bounds and "
                    "dependence model for every study variable."
                ),
            ),
            ResearchAcceptanceItem(
                key="sampling_convergence",
                title="Sampling-size and domain convergence",
                state=ResearchEvidenceState.IMPLEMENTED,
                evidence=(
                    "Seeded LHS generation and reproducible dataset splitting are implemented."
                ),
                remaining=(
                    "Demonstrate that the adopted sample size and bounds adequately cover the "
                    "response/failure domain and that key metrics are stable with added samples."
                ),
            ),
            ResearchAcceptanceItem(
                key="surrogate_validation",
                title="ANN surrogate validation",
                state=ResearchEvidenceState.IMPLEMENTED,
                evidence=(
                    "Multi-output ANN training, held-out RMSE/MAE/R2 and fresh direct checks, "
                    "including near-limit-state error reporting, are implemented."
                ),
                remaining=(
                    "Train the final study model and meet pre-declared acceptance criteria on "
                    "held-out and near-g=0 validation data."
                ),
            ),
            ResearchAcceptanceItem(
                key="reliability_cross_check",
                title="Reliability-method cross-check",
                state=ResearchEvidenceState.IMPLEMENTED,
                evidence=(
                    "FORM, ANN Monte Carlo and direct-evaluator Monte Carlo are implemented."
                ),
                remaining=(
                    "Review FORM convergence/design points and demonstrate acceptable agreement "
                    "between ANN and direct reliability estimates with uncertainty reporting."
                ),
            ),
            ResearchAcceptanceItem(
                key="target_reliability",
                title="Target reliability basis",
                state=ResearchEvidenceState.NOT_STARTED,
                evidence="No hidden target reliability index is imposed by the software.",
                remaining=(
                    "Adopt a source-justified target beta/reference period appropriate to the "
                    "study's consequence/reliability class and governing framework."
                ),
            ),
            ResearchAcceptanceItem(
                key="rbdo_validation",
                title="RBDO objective and optimum validation",
                state=ResearchEvidenceState.IMPLEMENTED,
                evidence=(
                    "SLSQP optimisation with ANN/FORM reliability constraints is implemented."
                ),
                remaining=(
                    "Justify objective coefficients and design bounds, then independently "
                    "re-evaluate the final optimum with the direct deterministic/reliability "
                    "model before accepting it."
                ),
            ),
        )
    )
