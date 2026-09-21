from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO

from rc_single_span.analysis.grillage_solver import GrillageAnalysisResult
from rc_single_span.analysis.structural_model import StructuralModel
from rc_single_span.verification.comparison import (
    ComparisonTolerance,
    ScalarComparison,
    compare_scalar,
)
from rc_single_span.verification.member_forces import (
    native_global_member_end_forces,
)


@dataclass(frozen=True)
class ExternalResult:
    result_type: str
    object_id: int
    end: str
    component: str
    value: float
    unit: str
    source: str
    notes: str

    @property
    def key(self) -> tuple[str, int, str, str]:
        return self.result_type, self.object_id, self.end, self.component


@dataclass(frozen=True)
class StaadComparisonReport:
    comparisons: tuple[ScalarComparison, ...]
    missing_keys: tuple[tuple[str, int, str, str], ...]
    unexpected_keys: tuple[tuple[str, int, str, str], ...]

    @property
    def passes(self) -> bool:
        return (
            bool(self.comparisons)
            and not self.missing_keys
            and not self.unexpected_keys
            and all(item.passes for item in self.comparisons)
        )


def parse_external_results_csv(text: str) -> tuple[ExternalResult, ...]:
    reader = csv.DictReader(StringIO(text))
    required = {
        "result_type",
        "object_id",
        "end",
        "component",
        "external_value",
        "unit",
        "source",
        "notes",
    }
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise ValueError("External results CSV is missing required columns.")

    rows: list[ExternalResult] = []
    seen: set[tuple[str, int, str, str]] = set()
    for raw in reader:
        value_text = (raw.get("external_value") or "").strip()
        if not value_text:
            continue
        item = ExternalResult(
            result_type=(raw.get("result_type") or "").strip(),
            object_id=int((raw.get("object_id") or "").strip()),
            end=(raw.get("end") or "").strip(),
            component=(raw.get("component") or "").strip().upper(),
            value=float(value_text),
            unit=(raw.get("unit") or "").strip(),
            source=(raw.get("source") or "").strip(),
            notes=(raw.get("notes") or "").strip(),
        )
        if not item.result_type or not item.component:
            raise ValueError("External result type/component cannot be empty.")
        if item.key in seen:
            raise ValueError(f"Duplicate external result key: {item.key}.")
        seen.add(item.key)
        rows.append(item)
    return tuple(rows)


def _expected(
    model: StructuralModel,
    analysis: GrillageAnalysisResult,
) -> dict[tuple[str, int, str, str], tuple[float, str]]:
    result: dict[tuple[str, int, str, str], tuple[float, str]] = {}
    support_ids = {item.node_id for item in model.supports}

    for node in analysis.nodes:
        result[("node_displacement", node.node_id, "", "DZ")] = (
            node.vertical_displacement_m,
            "m",
        )
        if node.node_id in support_ids:
            result[("support_reaction", node.node_id, "", "FZ")] = (
                node.vertical_reaction_kn,
                "kN",
            )

    for item in native_global_member_end_forces(model, analysis):
        result[("member_end_force", item.member_id, item.end, "FZ")] = (
            item.fz_kn,
            "kN",
        )
        result[("member_end_force", item.member_id, item.end, "MX")] = (
            item.mx_knm,
            "kNm",
        )
        result[("member_end_force", item.member_id, item.end, "MY")] = (
            item.my_knm,
            "kNm",
        )
    return result


def _default_tolerance(
    result_type: str,
    component: str,
) -> ComparisonTolerance:
    if result_type == "node_displacement":
        return ComparisonTolerance(relative=0.001, absolute=1.0e-6)
    if result_type == "support_reaction":
        return ComparisonTolerance(relative=0.001, absolute=0.1)
    if result_type == "member_end_force":
        return ComparisonTolerance(relative=0.001, absolute=0.1)
    return ComparisonTolerance()


def compare_staad_external_results(
    model: StructuralModel,
    analysis: GrillageAnalysisResult,
    external_csv: str,
    *,
    tolerance_overrides: dict[
        tuple[str, str], ComparisonTolerance
    ] | None = None,
) -> StaadComparisonReport:
    """Compare a populated STAAD return template against native global results."""

    expected = _expected(model, analysis)
    external_rows = parse_external_results_csv(external_csv)
    external = {item.key: item for item in external_rows}
    expected_keys = set(expected)
    external_keys = set(external)

    comparisons: list[ScalarComparison] = []
    for key in sorted(expected_keys & external_keys):
        reference_value, unit = expected[key]
        item = external[key]
        if item.unit != unit:
            raise ValueError(
                f"Unit mismatch for {key}: expected {unit}, received {item.unit}."
            )
        override_key = (item.result_type, item.component)
        tolerance = (
            tolerance_overrides.get(override_key)
            if tolerance_overrides and override_key in tolerance_overrides
            else _default_tolerance(item.result_type, item.component)
        )
        comparisons.append(
            compare_scalar(
                label=":".join(
                    (
                        item.result_type,
                        str(item.object_id),
                        item.end or "-",
                        item.component,
                    )
                ),
                internal_value=reference_value,
                reference_value=item.value,
                tolerance=tolerance,
                unit=unit,
                source=item.source or "STAAD",
            )
        )

    return StaadComparisonReport(
        comparisons=tuple(comparisons),
        missing_keys=tuple(sorted(expected_keys - external_keys)),
        unexpected_keys=tuple(sorted(external_keys - expected_keys)),
    )
