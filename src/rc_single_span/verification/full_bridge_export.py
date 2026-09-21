from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from rc_single_span.analysis.permanent import PermanentLoadCategory
from rc_single_span.codes.bs5400.combinations import BS5400PrimaryTraffic
from rc_single_span.codes.eurocode.combinations import (
    EurocodeCombinationFactors,
    EurocodeServiceabilityFactors,
)
from rc_single_span.core.models import BridgeProject, PermanentActionStage
from rc_single_span.traffic.bs5400 import BS5400NominalTrafficSuite
from rc_single_span.traffic.combinations import (
    BS5400GirderCombinationResult,
    EurocodeGirderCombinationResult,
    build_bs5400_project_combinations,
    build_eurocode_project_combinations,
)
from rc_single_span.verification.full_bridge import (
    FullBridgeVerificationSuite,
    build_full_bridge_verification_suite,
)
from rc_single_span.verification.full_bridge_campaign import (
    CrossStageCombinationRule,
    FullBridgeTrafficCampaign,
    FullBridgeTrafficSearchConfig,
    PermanentComponentSuite,
    TrafficAction,
    build_cross_stage_combination_rules,
    build_permanent_component_suite,
    run_full_bridge_traffic_campaign,
)
from rc_single_span.verification.package import StaadVerificationPackage


@dataclass(frozen=True)
class FullBridgeBundleResult:
    output_directory: Path
    index_path: Path
    written_files: tuple[Path, ...]
    stage_suite: FullBridgeVerificationSuite
    permanent_components: PermanentComponentSuite
    traffic_campaign: FullBridgeTrafficCampaign
    combination_rules: tuple[CrossStageCombinationRule, ...]
    eurocode_combinations: tuple[EurocodeGirderCombinationResult, ...]
    bs5400_combinations: tuple[BS5400GirderCombinationResult, ...]


def _package_files(
    root: Path,
    *,
    relative_directory: Path,
    base_name: str,
    package: StaadVerificationPackage,
    written: list[Path],
) -> list[str]:
    directory = root / relative_directory
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for name, text in package.files(base_name).items():
        path = directory / name
        path.write_text(text, encoding="utf-8")
        written.append(path)
        paths.append(path.relative_to(root).as_posix())
    return paths


def _write_text(
    root: Path,
    relative_path: str,
    text: str,
    written: list[Path],
) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    written.append(path)
    return path


def _combination_rules_csv(
    rules: tuple[CrossStageCombinationRule, ...],
) -> str:
    stream = StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        (
            "rule_id",
            "standard",
            "name",
            "traffic_action",
            "structural_dead_factor",
            "surfacing_factor",
            "other_superimposed_factor",
            "traffic_factor",
            "application_basis",
        )
    )
    for rule in rules:
        writer.writerow(
            (
                rule.rule_id,
                rule.standard,
                rule.name,
                rule.traffic_action.value,
                format(
                    rule.permanent_factors[PermanentLoadCategory.STRUCTURAL_DEAD],
                    ".17g",
                ),
                format(
                    rule.permanent_factors[PermanentLoadCategory.SURFACING],
                    ".17g",
                ),
                format(
                    rule.permanent_factors[PermanentLoadCategory.OTHER_SUPERIMPOSED],
                    ".17g",
                ),
                format(rule.traffic_factor, ".17g"),
                rule.application_basis,
            )
        )
    return stream.getvalue()


def _source_case_ids(
    campaign: FullBridgeTrafficCampaign,
    *,
    action: TrafficAction,
    girder_index: int,
) -> tuple[int, int, int]:
    search = {
        TrafficAction.LM1: campaign.lm1,
        TrafficAction.HA: campaign.ha,
        TrafficAction.HB: campaign.hb,
        TrafficAction.HA_HB: campaign.ha_hb,
    }[action]
    girder = search.girders[girder_index - 1]
    return (
        girder.moment_knm.case_id,
        girder.shear_kn.case_id,
        girder.torsion_knm.case_id,
    )


def _combination_envelopes_csv(
    campaign: FullBridgeTrafficCampaign,
    eurocode: tuple[EurocodeGirderCombinationResult, ...],
    bs5400: tuple[BS5400GirderCombinationResult, ...],
) -> str:
    stream = StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        (
            "standard",
            "girder_index",
            "rule_id",
            "combination_name",
            "traffic_action",
            "governing_components",
            "moment_knm",
            "shear_kn",
            "torsion_knm",
            "moment_source_case_id",
            "shear_source_case_id",
            "torsion_source_case_id",
            "factors_json",
        )
    )

    for item in eurocode:
        source_ids = _source_case_ids(
            campaign,
            action=TrafficAction.LM1,
            girder_index=item.girder_index,
        )
        rows = (
            ("ec_uls_persistent", item.combinations.persistent_uls),
            ("ec_sls_characteristic", item.combinations.characteristic_sls),
            ("ec_sls_frequent", item.combinations.frequent_sls),
            ("ec_sls_quasi_permanent", item.combinations.quasi_permanent_sls),
        )
        for rule_id, combination in rows:
            writer.writerow(
                (
                    "Eurocode",
                    item.girder_index,
                    rule_id,
                    combination.name,
                    TrafficAction.LM1.value,
                    "moment;shear;torsion",
                    format(combination.effects.moment_knm, ".17g"),
                    format(combination.effects.shear_kn, ".17g"),
                    format(combination.effects.torsion_knm, ".17g"),
                    *source_ids,
                    json.dumps(combination.factors, sort_keys=True),
                )
            )

    traffic_action = {
        BS5400PrimaryTraffic.HA: TrafficAction.HA,
        BS5400PrimaryTraffic.HB: TrafficAction.HB,
        BS5400PrimaryTraffic.HA_HB: TrafficAction.HA_HB,
    }
    for item in bs5400:
        governing_lookup = {(row.combination, row.limit_state): row for row in item.governing}
        for case in item.cases:
            action = traffic_action[case.traffic]
            source_ids = _source_case_ids(
                campaign,
                action=action,
                girder_index=item.girder_index,
            )
            governing = governing_lookup[(case.combination, case.limit_state)]
            governing_components = ";".join(
                quantity
                for quantity, source in governing.governing_sources.items()
                if source is case.traffic
            )
            rule_id = f"bs_combination_{case.combination}_{case.limit_state.value}_{action.value}"
            writer.writerow(
                (
                    "BS 5400",
                    item.girder_index,
                    rule_id,
                    case.result.name,
                    action.value,
                    governing_components,
                    format(case.result.effects.moment_knm, ".17g"),
                    format(case.result.effects.shear_kn, ".17g"),
                    format(case.result.effects.torsion_knm, ".17g"),
                    *source_ids,
                    json.dumps(case.result.factors, sort_keys=True),
                )
            )
    return stream.getvalue()


def _combination_application_matrix(
    *,
    rules: tuple[CrossStageCombinationRule, ...],
    permanent_suite: PermanentComponentSuite,
    campaign: FullBridgeTrafficCampaign,
    permanent_model_paths: dict[str, str],
    traffic_model_paths: dict[str, str],
) -> tuple[str, str, int]:
    stream = StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(
        (
            "combination_instance_id",
            "rule_id",
            "standard",
            "traffic_action",
            "source_kind",
            "source_key",
            "source_model_path",
            "load_case_id",
            "stage",
            "permanent_category",
            "factor",
        )
    )
    instances: list[dict[str, object]] = []

    for rule in rules:
        for traffic_case in campaign.cases_for(rule.traffic_action):
            instance_id = f"{rule.rule_id}__{traffic_case.case_key}"
            terms: list[dict[str, object]] = []
            for component in permanent_suite.components:
                factor = rule.permanent_factors[component.category]
                term = {
                    "source_kind": "permanent_component",
                    "source_key": component.component_key,
                    "source_model_path": permanent_model_paths[component.component_key],
                    "load_case_id": component.analysis.load_case_id,
                    "stage": component.stage.value,
                    "permanent_category": component.category.value,
                    "factor": factor,
                }
                terms.append(term)
                writer.writerow(
                    (
                        instance_id,
                        rule.rule_id,
                        rule.standard,
                        rule.traffic_action.value,
                        term["source_kind"],
                        term["source_key"],
                        term["source_model_path"],
                        term["load_case_id"],
                        term["stage"],
                        term["permanent_category"],
                        format(float(factor), ".17g"),
                    )
                )

            traffic_term = {
                "source_kind": "traffic_case",
                "source_key": traffic_case.case_key,
                "source_model_path": traffic_model_paths[traffic_case.case_key],
                "load_case_id": traffic_case.analysis.load_case_id,
                "stage": PermanentActionStage.SUPERIMPOSED.value,
                "permanent_category": "",
                "factor": rule.traffic_factor,
            }
            terms.append(traffic_term)
            writer.writerow(
                (
                    instance_id,
                    rule.rule_id,
                    rule.standard,
                    rule.traffic_action.value,
                    traffic_term["source_kind"],
                    traffic_term["source_key"],
                    traffic_term["source_model_path"],
                    traffic_term["load_case_id"],
                    traffic_term["stage"],
                    traffic_term["permanent_category"],
                    format(rule.traffic_factor, ".17g"),
                )
            )
            instances.append(
                {
                    "combination_instance_id": instance_id,
                    "rule_id": rule.rule_id,
                    "standard": rule.standard,
                    "name": rule.name,
                    "traffic_action": rule.traffic_action.value,
                    "application_basis": rule.application_basis,
                    "terms": terms,
                }
            )

    return (
        stream.getvalue(),
        json.dumps(
            {
                "schema_version": 1,
                "combination_instance_count": len(instances),
                "application_note": (
                    "Factors apply to response components returned from each source "
                    "model. The source models intentionally retain their load-time "
                    "stiffness; this is not a same-stiffness STAAD LOAD COMB list."
                ),
                "instances": instances,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        len(instances),
    )


def _bundle_readme(
    *,
    stage_count: int,
    component_count: int,
    traffic_count: int,
    rule_count: int,
    combination_instance_count: int,
) -> str:
    return f"""# Full seven-girder STAAD verification bundle

This bundle contains coordinated full-width models for the 15 m reference
bridge. Every structural model contains all seven physical longitudinal girder
lines. The final-composite and traffic models also contain transverse deck
members and therefore capture transverse distribution and torsion.

## Inventory

- {stage_count} complete construction-stage models;
- {component_count} category-separated permanent-action models;
- {traffic_count} retained governing traffic models across LM1, HA, HB and HA+HB;
- {rule_count} Eurocode/BS 5400 combination rules; and
- {combination_instance_count} explicit rule-by-traffic-case applications.

Each model directory contains a `.std` file, provenance manifest, internal
expected-results CSV and empty STAAD-results return template.

## Structural-stage rule

The precast and wet-deck files contain all seven girders in one coordinated
model, but do not invent transverse stiffness before the in-situ slab hardens.
No diaphragm properties are present in the project input. The final composite
stage activates the connected orthogonal deck grillage.

Early permanent actions must not be reapplied to the final-composite stiffness.
For that reason `combination_application_matrix.csv` and `.json` specify
response superposition across the stage-correct source models. A single
same-stiffness STAAD `LOAD COMB` would produce the wrong construction-stage
deflection and can also misrepresent locked-in early-stage response.

`combination_envelopes.csv` contains the internal per-girder force envelopes for
the implemented Eurocode and BS 5400 rules. It is a comparison target, not a
substitute for genuine STAAD results.

## External status

Generation and internal equilibrium checks are complete. Independent STAAD
verification remains **pending** until the `.std` files are run in STAAD.Pro,
the matching return templates are populated from genuine output, and the
results are compared. Do not copy internal expected values into return files.
"""


def write_full_bridge_verification_bundle(
    project: BridgeProject,
    output_directory: str | Path,
    *,
    elastic_modulus_basis: str,
    eurocode_sls_factors: EurocodeServiceabilityFactors,
    eurocode_uls_factors: EurocodeCombinationFactors | None = None,
    repository_sha: str | None = None,
    longitudinal_divisions: int = 8,
    traffic_config: FullBridgeTrafficSearchConfig | None = None,
) -> FullBridgeBundleResult:
    """Write the complete staged and traffic seven-girder STAAD campaign."""

    elastic_modulus_mpa = project.materials.elastic_modulus_mpa
    if elastic_modulus_mpa is None or elastic_modulus_mpa <= 0.0:
        raise ValueError("Full-bridge verification bundle requires explicit elastic_modulus_mpa.")
    if not elastic_modulus_basis.strip():
        raise ValueError("elastic_modulus_basis cannot be empty.")

    root = Path(output_directory)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(
            "Full-bridge bundle output directory must be absent or empty to prevent "
            "stale verification files."
        )
    root.mkdir(parents=True, exist_ok=True)

    stage_suite = build_full_bridge_verification_suite(
        project,
        longitudinal_divisions=longitudinal_divisions,
    )
    permanent_suite = build_permanent_component_suite(
        project,
        longitudinal_divisions=longitudinal_divisions,
    )
    campaign = run_full_bridge_traffic_campaign(
        project,
        config=traffic_config,
    )
    rules = build_cross_stage_combination_rules(
        eurocode_sls_factors=eurocode_sls_factors,
        eurocode_uls_factors=eurocode_uls_factors,
    )
    eurocode = build_eurocode_project_combinations(
        project,
        campaign.lm1,
        sls_factors=eurocode_sls_factors,
        uls_factors=eurocode_uls_factors,
    )
    bs_suite = BS5400NominalTrafficSuite(
        ha=campaign.ha,
        hb=campaign.hb,
        ha_hb=campaign.ha_hb,
        application_status=(
            "Full-width STAAD campaign retains every case governing a reported "
            "girder response component."
        ),
    )
    bs5400 = build_bs5400_project_combinations(project, bs_suite)

    written: list[Path] = []
    stage_entries: list[dict[str, object]] = []
    for item in stage_suite.stages:
        label = (
            "final_composite"
            if item.stage is PermanentActionStage.SUPERIMPOSED
            else item.stage.value
        )
        files = _package_files(
            root,
            relative_directory=Path("stages") / label,
            base_name=f"full_bridge_{label}",
            package=item.staad_package,
            written=written,
        )
        stage_entries.append(
            {
                "stage": item.stage.value,
                "model_label": label,
                "node_count": len(item.model.nodes),
                "member_count": len(item.model.beams),
                "longitudinal_member_count": item.longitudinal_member_count,
                "transverse_member_count": item.transverse_member_count,
                "transverse_system_active": item.transverse_system_active,
                "structural_system_basis": item.structural_system_basis,
                "load_case_id": item.analysis.load_case_id,
                "files": files,
            }
        )

    permanent_entries: list[dict[str, object]] = []
    permanent_model_paths: dict[str, str] = {}
    for item in permanent_suite.components:
        files = _package_files(
            root,
            relative_directory=Path("permanent_components") / item.component_key,
            base_name=item.component_key,
            package=item.staad_package,
            written=written,
        )
        std_path = next(path for path in files if path.endswith(".std"))
        permanent_model_paths[item.component_key] = std_path
        permanent_entries.append(
            {
                "component_key": item.component_key,
                "stage": item.stage.value,
                "category": item.category.value,
                "characteristic_resultant_kn": item.characteristic_resultant_kn,
                "load_case_id": item.analysis.load_case_id,
                "files": files,
            }
        )

    traffic_entries: list[dict[str, object]] = []
    traffic_model_paths: dict[str, str] = {}
    for item in campaign.cases:
        files = _package_files(
            root,
            relative_directory=Path("traffic") / item.action.value / item.case_key,
            base_name=item.case_key,
            package=item.staad_package,
            written=written,
        )
        std_path = next(path for path in files if path.endswith(".std"))
        traffic_model_paths[item.case_key] = std_path
        traffic_entries.append(
            {
                "case_key": item.case_key,
                "standard": item.standard,
                "action": item.action.value,
                "source_case_id": item.source_case_id,
                "description": item.description,
                "governing_for": list(item.governing_for),
                "node_count": len(item.model.nodes),
                "member_count": len(item.model.beams),
                "load_case_id": item.analysis.load_case_id,
                "files": files,
            }
        )

    rules_path = _write_text(
        root,
        "combination_rules.csv",
        _combination_rules_csv(rules),
        written,
    )
    envelope_path = _write_text(
        root,
        "combination_envelopes.csv",
        _combination_envelopes_csv(campaign, eurocode, bs5400),
        written,
    )
    matrix_csv, matrix_json, instance_count = _combination_application_matrix(
        rules=rules,
        permanent_suite=permanent_suite,
        campaign=campaign,
        permanent_model_paths=permanent_model_paths,
        traffic_model_paths=traffic_model_paths,
    )
    matrix_csv_path = _write_text(
        root,
        "combination_application_matrix.csv",
        matrix_csv,
        written,
    )
    matrix_json_path = _write_text(
        root,
        "combination_application_matrix.json",
        matrix_json,
        written,
    )
    readme_path = _write_text(
        root,
        "README.md",
        _bundle_readme(
            stage_count=len(stage_entries),
            component_count=len(permanent_entries),
            traffic_count=len(traffic_entries),
            rule_count=len(rules),
            combination_instance_count=instance_count,
        ),
        written,
    )

    index = {
        "schema_version": 2,
        "project_name": project.name,
        "span_m": float(project.geometry.span_m),
        "deck_width_m": float(project.geometry.deck_width_m),
        "girder_count": int(project.geometry.girder_count),
        "girder_spacing_m": float(project.geometry.girder_spacing_m),
        "elastic_modulus_mpa": float(elastic_modulus_mpa),
        "elastic_modulus_basis": elastic_modulus_basis.strip(),
        "repository_sha": repository_sha or "",
        "longitudinal_stage_divisions": longitudinal_divisions,
        "full_width_stage_model_count": len(stage_entries),
        "permanent_component_model_count": len(permanent_entries),
        "governing_traffic_model_count": len(traffic_entries),
        "combination_rule_count": len(rules),
        "combination_instance_count": instance_count,
        "eurocode_sls_factors": {
            "psi1_traffic": eurocode_sls_factors.psi1_traffic,
            "psi2_traffic": eurocode_sls_factors.psi2_traffic,
        },
        "eurocode_uls_factors": {
            "gamma_g_unfavourable": (
                eurocode_uls_factors or EurocodeCombinationFactors()
            ).gamma_g_unfavourable,
            "gamma_g_favourable": (
                eurocode_uls_factors or EurocodeCombinationFactors()
            ).gamma_g_favourable,
            "gamma_q_traffic": (
                eurocode_uls_factors or EurocodeCombinationFactors()
            ).gamma_q_traffic,
        },
        "traffic_search": {
            "lm1": {
                "evaluated_case_count": campaign.lm1.evaluated_case_count,
                "retained_governing_case_count": len(campaign.cases_for(TrafficAction.LM1)),
                "longitudinal_step_m": campaign.lm1.longitudinal_step_m,
                "tandem_combinations_exhaustive": (campaign.lm1.tandem_combinations_exhaustive),
                "search_strategy": campaign.lm1.search_strategy,
            },
            "ha": {
                "evaluated_case_count": campaign.ha.evaluated_case_count,
                "retained_governing_case_count": len(campaign.cases_for(TrafficAction.HA)),
                "longitudinal_step_m": campaign.ha.longitudinal_step_m,
                "kel_combinations_exhaustive": (campaign.ha.kel_combinations_exhaustive),
            },
            "hb": {
                "evaluated_case_count": campaign.hb.evaluated_case_count,
                "retained_governing_case_count": len(campaign.cases_for(TrafficAction.HB)),
                "longitudinal_step_m": campaign.hb.longitudinal_step_m,
                "transverse_step_m": campaign.hb.transverse_step_m,
                "checked_inner_axle_spacings_m": list(campaign.hb.checked_inner_axle_spacings_m),
            },
            "ha_hb": {
                "evaluated_case_count": campaign.ha_hb.evaluated_case_count,
                "retained_governing_case_count": len(campaign.cases_for(TrafficAction.HA_HB)),
                "hb_longitudinal_step_m": (campaign.ha_hb.hb_longitudinal_step_m),
                "hb_transverse_step_m": campaign.ha_hb.hb_transverse_step_m,
                "ha_kel_step_m": campaign.ha_hb.ha_kel_step_m,
                "ha_assignment_search_exhaustive": (campaign.ha_hb.ha_assignment_search_exhaustive),
                "kel_combinations_exhaustive": (campaign.ha_hb.kel_combinations_exhaustive),
            },
        },
        "stage_models": stage_entries,
        "permanent_components": permanent_entries,
        "traffic_models": traffic_entries,
        "combination_files": {
            "rules_csv": rules_path.relative_to(root).as_posix(),
            "application_matrix_csv": matrix_csv_path.relative_to(root).as_posix(),
            "application_matrix_json": matrix_json_path.relative_to(root).as_posix(),
            "internal_envelopes_csv": envelope_path.relative_to(root).as_posix(),
        },
        "readme": readme_path.relative_to(root).as_posix(),
        "internal_status": "passed",
        "external_verification_status": "pending",
        "external_verification_note": (
            "Run the full-width .std files in STAAD.Pro and return genuine result "
            "tables before promoting structural-analysis verification."
        ),
    }
    index_path = _write_text(
        root,
        "bundle_index.json",
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        written,
    )
    return FullBridgeBundleResult(
        output_directory=root,
        index_path=index_path,
        written_files=tuple(written),
        stage_suite=stage_suite,
        permanent_components=permanent_suite,
        traffic_campaign=campaign,
        combination_rules=rules,
        eurocode_combinations=eurocode,
        bs5400_combinations=bs5400,
    )
