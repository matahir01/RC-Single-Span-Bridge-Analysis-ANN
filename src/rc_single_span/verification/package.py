from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from io import StringIO

from rc_single_span.analysis.grillage_solver import GrillageAnalysisResult
from rc_single_span.analysis.structural_model import StructuralModel
from rc_single_span.verification.staad_export import (
    export_staad_std,
    staad_support_restraints,
)


@dataclass(frozen=True)
class StaadVerificationPackage:
    staad_std: str
    manifest_json: str
    expected_results_csv: str
    external_results_template_csv: str

    def files(self, base_name: str = "single_span_verification") -> dict[str, str]:
        stem = re.sub(r"[^A-Za-z0-9_-]", "_", base_name.strip()).strip("_")
        if not stem:
            raise ValueError("Verification package base_name cannot be empty.")
        return {
            f"{stem}.std": self.staad_std,
            f"{stem}_manifest.json": self.manifest_json,
            f"{stem}_expected_results.csv": self.expected_results_csv,
            f"{stem}_external_results_template.csv": self.external_results_template_csv,
        }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _float(value: float) -> str:
    return format(float(value), ".17g")


def _expected_results_csv(analysis: GrillageAnalysisResult) -> str:
    stream = StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        (
            "result_type",
            "object_id",
            "end",
            "component",
            "value",
            "unit",
            "comparison_status",
        )
    )
    for node in analysis.nodes:
        writer.writerow(
            (
                "node_displacement",
                node.node_id,
                "",
                "native_DZ",
                _float(node.vertical_displacement_m),
                "m",
                "direct",
            )
        )
        writer.writerow(
            (
                "support_reaction",
                node.node_id,
                "",
                "native_FZ",
                _float(node.vertical_reaction_kn),
                "kN",
                "direct",
            )
        )

    for member in analysis.members:
        rows = (
            ("i", "native_vertical_shear", member.i_vertical_force_kn, "kN"),
            (
                "i",
                "native_vertical_bending",
                member.i_vertical_bending_moment_knm,
                "kNm",
            ),
            ("i", "native_torsion", member.i_torsion_knm, "kNm"),
            ("j", "native_vertical_shear", member.j_vertical_force_kn, "kN"),
            (
                "j",
                "native_vertical_bending",
                member.j_vertical_bending_moment_knm,
                "kNm",
            ),
            ("j", "native_torsion", member.j_torsion_knm, "kNm"),
        )
        for end, component, value, unit in rows:
            writer.writerow(
                (
                    "member_end_force",
                    member.member_id,
                    end,
                    component,
                    _float(value),
                    unit,
                    "requires_explicit_staad_axis_mapping",
                )
            )
    return stream.getvalue()


def _external_results_template_csv(analysis: GrillageAnalysisResult) -> str:
    stream = StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        (
            "result_type",
            "object_id",
            "end",
            "component",
            "external_value",
            "unit",
            "source",
            "notes",
        )
    )
    for node in analysis.nodes:
        writer.writerow(
            (
                "node_displacement",
                node.node_id,
                "",
                "DZ",
                "",
                "m",
                "STAAD",
                "",
            )
        )
        if abs(node.vertical_reaction_kn) > 1.0e-12:
            writer.writerow(
                (
                    "support_reaction",
                    node.node_id,
                    "",
                    "FZ",
                    "",
                    "kN",
                    "STAAD",
                    "",
                )
            )
    for member in analysis.members:
        for end in ("i", "j"):
            for component, unit in (
                ("vertical_shear", "kN"),
                ("vertical_bending", "kNm"),
                ("torsion", "kNm"),
            ):
                writer.writerow(
                    (
                        "member_end_force",
                        member.member_id,
                        end,
                        component,
                        "",
                        unit,
                        "STAAD",
                        "Populate only after explicit STAAD/native axis mapping is confirmed.",
                    )
                )
    return stream.getvalue()


def build_staad_verification_package(
    model: StructuralModel,
    analysis: GrillageAnalysisResult,
    *,
    provenance: dict[str, str] | None = None,
) -> StaadVerificationPackage:
    """Build one traceable STAAD package for the exact solved common grillage."""

    if analysis.load_case_id not in {case.load_case_id for case in model.load_cases}:
        raise ValueError("Analysis load case is absent from the exported structural model.")
    case = next(
        item for item in model.load_cases if item.load_case_id == analysis.load_case_id
    )
    if case.name != analysis.load_case_name:
        raise ValueError("Analysis and model load-case names are inconsistent.")

    staad = export_staad_std(model)
    expected = _expected_results_csv(analysis)
    external_template = _external_results_template_csv(analysis)
    restraints = staad_support_restraints(model)
    extra_ux = [item.node_id for item in restraints if item.ux]
    extra_uy = [item.node_id for item in restraints if item.uy]

    manifest = {
        "schema_version": 1,
        "model_name": model.name,
        "load_case_id": analysis.load_case_id,
        "load_case_name": analysis.load_case_name,
        "units": {"length": "m", "force": "kN", "moment": "kNm"},
        "node_count": len(model.nodes),
        "member_count": len(model.beams),
        "section_count": len(model.sections),
        "native_solver": "vertical grillage: w, rx, ry DOFs",
        "external_solver": "STAAD SPACE",
        "staad_stabilization": {
            "reason": (
                "STAAD carries in-plane rigid-body DOFs absent from the native "
                "vertical-only grillage solver."
            ),
            "ux_restrained_nodes": extra_ux,
            "uy_restrained_nodes": extra_uy,
            "vertical_restraints": "copied from the native support set",
            "claim": (
                "These added in-plane restraints are stabilization only and must not "
                "be interpreted as physical bearing restraints."
            ),
        },
        "comparison_scope": {
            "direct_now": ["support FZ reactions", "joint vertical DZ displacements"],
            "requires_axis_mapping_before_acceptance": [
                "member vertical shear",
                "member vertical bending moment",
                "member torsion",
            ],
        },
        "equilibrium": {
            "applied_vertical_load_kn": analysis.total_applied_vertical_load_kn,
            "vertical_reaction_kn": analysis.total_vertical_reaction_kn,
            "residual_kn": analysis.vertical_equilibrium_residual_kn,
        },
        "provenance": provenance or {},
        "files": {
            "staad_std": {"sha256": _sha256(staad), "extension": ".std"},
            "expected_results_csv": {
                "sha256": _sha256(expected),
                "extension": ".csv",
            },
            "external_results_template_csv": {
                "sha256": _sha256(external_template),
                "extension": ".csv",
            },
        },
        "verification_note": (
            "The package exports the exact common-grillage model already solved by "
            "the internal engine. It is evidence infrastructure, not independent "
            "verification by itself. Acceptance state changes only after genuine "
            "external results are returned and compared."
        ),
    }
    return StaadVerificationPackage(
        staad_std=staad,
        manifest_json=json.dumps(manifest, indent=2, sort_keys=True),
        expected_results_csv=expected,
        external_results_template_csv=external_template,
    )
