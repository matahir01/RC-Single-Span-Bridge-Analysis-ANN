"""Convergence control for BS EN 1991-2 LM1 influence-surface searches.

This module deliberately wraps the response-specific influence-surface search
rather than the historical full-lane UDL search.  A convergence result is only
accepted when every tandem-position vector at every refinement is exhaustive.
"""

from __future__ import annotations

from rc_single_span.codes.eurocode.lm1 import LM1AdjustmentFactors
from rc_single_span.core.models import BridgeProject
from rc_single_span.traffic.lm1 import (
    LM1ConvergenceResult,
    LM1ConvergenceStep,
    LM1SearchResult,
)
from rc_single_span.traffic.lm1_influence import run_lm1_influence_grillage_search


def _influence_refinement(
    coarse: LM1SearchResult,
    fine: LM1SearchResult,
) -> LM1ConvergenceStep:
    """Return the largest girder-envelope change between two LM1 searches."""

    if len(coarse.girders) != len(fine.girders):
        raise RuntimeError("LM1 girder count changed during convergence refinement.")

    worst = (-1.0, "", 0)
    for coarse_girder, fine_girder in zip(coarse.girders, fine.girders, strict=True):
        for name, coarse_value, fine_value in (
            ("moment", coarse_girder.moment_knm.value, fine_girder.moment_knm.value),
            ("shear", coarse_girder.shear_kn.value, fine_girder.shear_kn.value),
            ("torsion", coarse_girder.torsion_knm.value, fine_girder.torsion_knm.value),
            (
                "deflection",
                coarse_girder.deflection_mm.value,
                fine_girder.deflection_mm.value,
            ),
        ):
            relative = abs(fine_value - coarse_value) / max(abs(fine_value), 1.0e-9)
            if relative > worst[0]:
                worst = (relative, name, fine_girder.girder_index)

    return LM1ConvergenceStep(
        coarse_step_m=coarse.longitudinal_step_m,
        fine_step_m=fine.longitudinal_step_m,
        maximum_relative_change=worst[0],
        governing_quantity=worst[1],
        girder_index=worst[2],
    )


def run_lm1_influence_grillage_search_converged(
    project: BridgeProject,
    *,
    factors: LM1AdjustmentFactors | None = None,
    initial_longitudinal_step_m: float = 2.4,
    minimum_longitudinal_step_m: float = 0.6,
    relative_tolerance: float = 0.05,
    max_refinements: int = 3,
    max_exhaustive_tandem_combinations: int = 5000,
) -> LM1ConvergenceResult:
    """Refine the BS EN LM1 influence-surface search until the envelope stabilises.

    The check compares the maximum moment, shear, torsion and deflection on
    every girder after halving the longitudinal tandem-placement step.  It
    refuses to certify a search that has fallen back to reduced tandem
    combinations; this prevents a numerically stable but incomplete search
    from being labelled converged.
    """

    if initial_longitudinal_step_m <= minimum_longitudinal_step_m:
        raise ValueError("Initial LM1 step must exceed the minimum step.")
    if not 0.0 < relative_tolerance < 1.0:
        raise ValueError("LM1 relative tolerance must lie in (0, 1).")
    if max_refinements < 1:
        raise ValueError("LM1 convergence requires at least one refinement.")

    current = run_lm1_influence_grillage_search(
        project,
        factors=factors,
        longitudinal_step_m=initial_longitudinal_step_m,
        max_exhaustive_tandem_combinations=max_exhaustive_tandem_combinations,
    )
    if not current.tandem_combinations_exhaustive:
        raise RuntimeError(
            "LM1 influence convergence cannot certify a reduced tandem search."
        )

    refinements: list[LM1ConvergenceStep] = []
    for _ in range(max_refinements):
        fine_step = max(
            minimum_longitudinal_step_m,
            current.longitudinal_step_m / 2.0,
        )
        if fine_step >= current.longitudinal_step_m - 1.0e-12:
            break

        fine = run_lm1_influence_grillage_search(
            project,
            factors=factors,
            longitudinal_step_m=fine_step,
            max_exhaustive_tandem_combinations=max_exhaustive_tandem_combinations,
        )
        if not fine.tandem_combinations_exhaustive:
            raise RuntimeError(
                "LM1 influence convergence cannot certify a reduced tandem search."
            )

        step = _influence_refinement(current, fine)
        refinements.append(step)
        current = fine
        if step.maximum_relative_change <= relative_tolerance:
            break
        if fine_step <= minimum_longitudinal_step_m + 1.0e-12:
            break

    return LM1ConvergenceResult(
        result=current,
        refinements=tuple(refinements),
        relative_tolerance=relative_tolerance,
    )
