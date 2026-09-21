from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from rc_single_span.core.models import BridgeProject
from rc_single_span.verification.construction import (
    ConstructionVerificationSuite,
    build_construction_verification_suite,
)


@dataclass(frozen=True)
class ConstructionBundleResult:
    output_directory: Path
    index_path: Path
    internal_crosscheck_path: Path
    written_files: tuple[Path, ...]
    suite: ConstructionVerificationSuite


def _comparison_csv(suite: ConstructionVerificationSuite) -> str:
    stream = StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        (
            "scope",
            "girder_index",
            "stage",
            "label",
            "internal_fe_value",
            "analytical_reference_value",
            "absolute_difference",
            "relative_difference",
            "unit",
            "status",
            "source",
        )
    )
    for item in suite.stages:
        for comparison in item.comparisons:
            writer.writerow(
                (
                    "stage",
                    item.girder_index,
                    item.stage.value,
                    comparison.label,
                    format(comparison.internal_value, ".17g"),
                    format(comparison.reference_value, ".17g"),
                    format(comparison.absolute_difference, ".17g"),
                    format(comparison.relative_difference, ".17g"),
                    comparison.unit,
                    comparison.status.value,
                    comparison.source,
                )
            )
    for item in suite.cumulative:
        for comparison in item.comparisons:
            writer.writerow(
                (
                    "cumulative",
                    item.girder_index,
                    "",
                    comparison.label,
                    format(comparison.internal_value, ".17g"),
                    format(comparison.reference_value, ".17g"),
                    format(comparison.absolute_difference, ".17g"),
                    format(comparison.relative_difference, ".17g"),
                    comparison.unit,
                    comparison.status.value,
                    comparison.source,
                )
            )
    return stream.getvalue()


def write_construction_verification_bundle(
    project: BridgeProject,
    output_directory: str | Path,
    *,
    elastic_modulus_basis: str,
    repository_sha: str | None = None,
    longitudinal_divisions: int = 8,
) -> ConstructionBundleResult:
    """Write the complete construction-stage STAAD verification package set.

    The bridge must already contain an explicit elastic modulus. The basis for
    that value is a mandatory provenance string so a verification archive cannot
    silently carry an unexplained stiffness assumption.
    """

    e_mpa = project.materials.elastic_modulus_mpa
    if e_mpa is None or e_mpa <= 0.0:
        raise ValueError(
            "Construction verification bundle requires explicit elastic_modulus_mpa."
        )
    if not elastic_modulus_basis.strip():
        raise ValueError("elastic_modulus_basis cannot be empty.")

    suite = build_construction_verification_suite(
        project,
        longitudinal_divisions=longitudinal_divisions,
    )
    if not suite.passes_internal_crosscheck:
        failed = [
            comparison.label
            for item in (*suite.stages, *suite.cumulative)
            for comparison in item.comparisons
            if not comparison.passes
        ]
        raise RuntimeError(
            "Construction verification bundle is blocked by failed internal "
            f"cross-checks: {', '.join(failed)}"
        )

    root = Path(output_directory)
    root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    entries: list[dict[str, object]] = []

    for item in suite.stages:
        stage_dir = (
            root
            / f"girder_{item.girder_index:02d}"
            / item.stage.value
        )
        stage_dir.mkdir(parents=True, exist_ok=True)
        base_name = f"g{item.girder_index:02d}_{item.stage.value}"
        package_files = item.staad_package.files(base_name)

        relative_paths: list[str] = []
        for name, text in package_files.items():
            path = stage_dir / name
            path.write_text(text, encoding="utf-8")
            written.append(path)
            relative_paths.append(path.relative_to(root).as_posix())

        entries.append(
            {
                "girder_index": item.girder_index,
                "stage": item.stage.value,
                "load_case_id": item.analysis.load_case_id,
                "load_case_name": item.analysis.load_case_name,
                "section_basis": item.reference.section.basis,
                "elastic_modulus_mpa": item.reference.elastic_modulus_mpa,
                "internal_crosscheck_passed": item.passes_internal_crosscheck,
                "files": relative_paths,
            }
        )

    crosscheck_path = root / "internal_crosscheck.csv"
    crosscheck_path.write_text(_comparison_csv(suite), encoding="utf-8")
    written.append(crosscheck_path)

    index = {
        "schema_version": 1,
        "project_name": project.name,
        "span_m": float(project.geometry.span_m),
        "girder_count": int(project.geometry.girder_count),
        "stage_model_count": len(suite.stages),
        "elastic_modulus_mpa": float(e_mpa),
        "elastic_modulus_basis": elastic_modulus_basis.strip(),
        "repository_sha": repository_sha or "",
        "longitudinal_verification_divisions": longitudinal_divisions,
        "internal_crosscheck_passed": suite.passes_internal_crosscheck,
        "external_verification_status": "pending",
        "external_verification_note": (
            "These files are prepared evidence inputs only. Run the .std models "
            "in STAAD.Pro, populate the external-results templates from genuine "
            "STAAD output, and compare those returns before promoting acceptance."
        ),
        "stage_models": entries,
        "internal_crosscheck_csv": crosscheck_path.relative_to(root).as_posix(),
    }
    index_path = root / "bundle_index.json"
    index_path.write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written.append(index_path)

    return ConstructionBundleResult(
        output_directory=root,
        index_path=index_path,
        internal_crosscheck_path=crosscheck_path,
        written_files=tuple(written),
        suite=suite,
    )
