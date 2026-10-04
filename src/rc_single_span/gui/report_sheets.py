"""Worked calculation sheets from a completed engine result, never UI estimates."""

from html import escape
from math import isclose

from rc_single_span.analysis.simple_span import (
    DistributedLoadSegment,
    PointLoadSegment,
    simple_span_mixed_load_response,
)
from rc_single_span.gui.engine_adapter import GuiCodeProfile
from rc_single_span.gui.report_diagrams import response_chart


def n(value: float) -> str:
    return f"{value:.4f}"


def strain_value(value: float) -> str:
    return f"{value:.8f}"


def row(reference: str, calculation: str, output: str, *, diagram: bool = False) -> str:
    if diagram:
        return (f"<tr><td colspan='3'><b>{escape(reference)} - {escape(output)}</b>"
                f"<br>{calculation}</td></tr>")
    return (f"<tr><td>{escape(reference).replace(chr(10), '<br>')}</td><td>{calculation}</td>"
            f"<td><b>{escape(output)}</b></td></tr>")


def sheet(number: int, title: str, project: str, rows: list[str]) -> str:
    return (
        f"<div class='sheet'><table class='sheet-head' cellspacing='0' cellpadding='5'>"
        "<tr><td width='60%'>"
        f"<b>Contract:</b> {escape(project)}<br>"
        f"<b>Part of structure:</b> RC single-span bridge<br>"
        f"<b>Calculation sheet:</b> {number}<br>{escape(title)}</td><td width='40%'>"
        "<b>Calculated by:</b> RC Bridge Analyzer<br>"
        "<b>Checked by:</b> __________________<br>"
        "<b>Independent review:</b> pending</td></tr></table>"
        f"<h2>{number}. {escape(title)}</h2>"
        "<table class='calculations' cellspacing='0' cellpadding='5'>"
        "<thead><tr><th>References</th>"
        "<th>Calculations</th><th>Output</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table></div>"
    )


def analysis_sheets(result, summary) -> str:
    rows = []
    span = float(result.project.geometry.span_m)
    for stage in (s for s in result.construction.stages if s.girder_index == 1):
        loads = "; ".join(
            f"{n(load.magnitude_kn_m)} kN/m, x = {n(load.x_start_m)} to "
            f"{n(load.x_end_m)} m ({escape(load.source)})"
            for load in stage.loads
        ) or "No distributed load"
        points = "; ".join(f"{n(load.magnitude_kn)} kN at x = {n(load.x_m)} m"
                           for load in stage.point_loads)
        r = stage.response
        rows.append(row(
            f"Construction\n{stage.stage.value.replace('_', ' ')}",
            f"Girder 1: {loads}; {points}<br>"
            f"Reactions = {n(r.reaction_left_kn)} / {n(r.reaction_right_kn)} kN; "
            f"Mmax = {n(r.max_moment_knm)} kNm at x = {n(r.max_moment_position_m)} m; "
            f"|V|max = {n(r.max_abs_shear_kn)} kN; "
            f"deflection = {n(stage.max_downward_deflection_mm)} mm.",
            "Stage analysed",
        ))
        contributions = [
            (load.magnitude_kn_m * (load.x_end_m - load.x_start_m),
             (load.x_start_m + load.x_end_m) / 2)
            for load in stage.loads
        ] + [(load.magnitude_kn, load.x_m) for load in stage.point_loads]
        total = sum(force for force, _ in contributions)
        moment_about_left = sum(force * centroid for force, centroid in contributions)
        right = moment_about_left / span
        left = total - right
        if not (isclose(left, r.reaction_left_kn, abs_tol=1e-6) and
                isclose(right, r.reaction_right_kn, abs_tol=1e-6)):
            raise ValueError("Construction-stage reaction substitution differs from engine result.")
        weight_terms = " + ".join(
            f"{n(load.magnitude_kn_m)} x ({n(load.x_end_m)} - {n(load.x_start_m)})"
            for load in stage.loads
        )
        if stage.point_loads:
            weight_terms += (" + " if weight_terms else "") + " + ".join(
                n(load.magnitude_kn) for load in stage.point_loads)
        rows.append(row(
            "Equilibrium",
            f"Girder 1, {escape(stage.stage.value)}: L = {n(span)} m. "
            f"W = Σ w(b-a) + Σ P = {weight_terms or '0'} = {n(total)} kN.<br>"
            f"Rright = Σ(Wi xbar_i) / L = {n(moment_about_left)} / {n(span)} "
            f"= {n(r.reaction_right_kn)} kN; "
            f"Rleft = W - Rright = {n(total)} - {n(r.reaction_right_kn)} "
            f"= {n(r.reaction_left_kn)} kN.",
            f"ΣV = {n(total - left - right)} kN",
        ))
        x_m = r.max_moment_position_m
        distributed_terms = []
        applied_moment = 0.0
        for load in stage.loads:
            loaded = min(max(x_m - load.x_start_m, 0.0),
                         load.x_end_m - load.x_start_m)
            if loaded > 0:
                centroid = load.x_start_m + loaded / 2
                applied_moment += load.magnitude_kn_m * loaded * (x_m - centroid)
                distributed_terms.append(f"{n(load.magnitude_kn_m)} x {n(loaded)} x "
                                         f"({n(x_m)} - {n(centroid)})")
        point_terms = [
            f"{n(load.magnitude_kn)} x ({n(x_m)} - {n(load.x_m)})"
            for load in stage.point_loads if load.x_m <= x_m
        ]
        applied_moment += sum(load.magnitude_kn * (x_m - load.x_m)
                              for load in stage.point_loads if load.x_m <= x_m)
        if not isclose(left * x_m - applied_moment, r.max_moment_knm, abs_tol=1e-6):
            raise ValueError("Construction-stage moment substitution differs from engine result.")
        substituted = " - ".join((f"{n(left)} x {n(x_m)}",
                                    *distributed_terms, *point_terms))
        rows.append(row(
            "Stage M, EI, δ",
            f"Girder 1, {escape(stage.stage.value)}: "
            "M(x) = Rleft x - Σw ℓ(x - xcentroid) - ΣP(x - xp). "
            f"At x = {n(x_m)} m: M = {substituted} = "
            f"{n(r.max_moment_knm)} kNm. "
            f"|V|max = {n(r.max_abs_shear_kn)} kN at "
            f"x = {n(r.max_abs_shear_position_m)} m.<br>"
            "δ(x) = ∫M(s)m_x(s) ds / EI using the stage section: "
            f"EI = {n(stage.elastic_modulus_mpa)} x 1000 x "
            f"{n(stage.section.iy_m4)} = "
            f"{n(stage.elastic_modulus_mpa * 1000 * stage.section.iy_m4)} "
            f"kNm²; δmax = {n(stage.max_downward_deflection_mm)} mm at "
            f"x = {n(stage.max_deflection_position_m)} m.",
            "Checked stage",
        ))
    if result.lm1 is not None:
        traffic = result.lm1
        rows.append(row("BS EN 1991-2 LM1",
                        f"{traffic.evaluated_case_count:,} tandem placements at "
                        f"{n(traffic.longitudinal_step_m)} m; "
                        f"{len(traffic.cases)} retained physical cases. "
                        f"Exhaustive: {traffic.tandem_combinations_exhaustive}.",
                        "Search record"))
        for item in result.eurocode_combinations:
            e = item.combinations.persistent_uls.effects
            rows.append(row("BS EN 1990 ULS envelope",
                f"Girder {item.girder_index}: MEd = {n(e.moment_knm)} kNm, "
                f"VEd = {n(e.shear_kn)} kN, TEd = {n(e.torsion_knm)} kNm. "
                "Each component is independently enveloped.",
                f"Girder {item.girder_index}"))
        for symbol, field, unit, girder in (
            ("M", "moment_knm", "kNm", summary.governing_moment.girder),
            ("V", "shear_kn", "kN", summary.governing_shear.girder),
            ("T", "torsion_knm", "kNm", summary.governing_torsion.girder),
        ):
            c = result.eurocode_combinations[girder - 1].combinations
            component = getattr(traffic.girders[girder - 1], field)
            rows.append(row("BS EN 1990 ULS",
                f"Girder {girder}: {symbol}Ed = gammaG x {symbol}G + "
                f"gammaQ x {symbol}LM1 = {n(c.persistent_uls.factors['G'])} x "
                f"{n(getattr(c.permanent_characteristic, field))} + "
                f"{n(c.persistent_uls.factors['Q_traffic'])} x "
                f"{n(getattr(c.traffic_characteristic, field))} = "
                f"{n(getattr(c.persistent_uls.effects, field))} {unit}. "
                f"Traffic case {component.case_id}, member {component.member_id}.",
                f"{n(getattr(c.persistent_uls.effects, field))} {unit}"))
    else:
        suite = result.bs_traffic
        rows.append(row("BS traffic grid",
            f"HA longitudinal = {n(suite.ha.longitudinal_step_m)} m; "
            f"HB longitudinal/transverse = {n(suite.hb.longitudinal_step_m)} / "
            f"{n(suite.hb.transverse_step_m)} m; HA+HB HB longitudinal/transverse "
            f"= {n(suite.ha_hb.hb_longitudinal_step_m)} / "
            f"{n(suite.ha_hb.hb_transverse_step_m)} m, KEL step = "
            f"{n(suite.ha_hb.ha_kel_step_m)} m. "
            "Support-anchored 15 m reference audit: default-to-half changed the "
            "maximum girder envelope by 6.809% (torsion, girder 5) and station shape "
            "by 26.510% (girder 7, x=7.2 m). Half-to-fine changed the envelope by "
            "1.894%, but station shape by 26.938% (girder 7, x=7.7 m). The 5% "
            "grid screen is not met; check the project grid before relying on it.",
            "Unverified grid"))
        for label, search in (("HA", suite.ha), ("HB", suite.hb), ("HA+HB", suite.ha_hb)):
            rows.append(row("BD 37/01", f"{label}: {search.evaluated_case_count:,} "
                            f"nominal placements, {len(search.cases)} retained cases. "
                            "Separate M/V/T/deflection case IDs.", "Search record"))
        for item in result.bs5400_combinations:
            uls = [c for c in item.governing if c.limit_state.value == "uls"]
            rows.append(row("BS 5400 ULS envelope",
                f"Girder {item.girder_index}: maximum over combinations 1-3 and "
                "HA/HB/HA+HB: "
                f"MEd = {n(max(c.effects.moment_knm for c in uls))} kNm; "
                f"VEd = {n(max(c.effects.shear_kn for c in uls))} kN; "
                f"TEd = {n(max(c.effects.torsion_knm for c in uls))} kNm. "
                "The design sheets identify each governing combination and case.",
                f"Girder {item.girder_index}"))
        governing_item = result.bs5400_combinations[summary.governing_moment.girder - 1]
        case = max((c for c in governing_item.cases if c.limit_state.value == "uls"),
                   key=lambda c: c.result.effects.moment_knm)
        g_terms = " + ".join(
            f"{n(case.result.factors[cat.value])} x {n(effect.moment_knm)}"
            for cat, effect in governing_item.permanent_characteristic_by_category.items())
        rows.append(row(f"BS 5400 combination {case.combination}",
            f"Girder {governing_item.girder_index}, {case.traffic.value}: "
            f"MEd = sum(gammafL,G x MG) + gammafL,Q x MQ = ({g_terms}) + "
            f"{n(case.result.factors['primary_live'])} x "
            f"{n(case.nominal_traffic.moment_knm)} = "
            f"{n(case.result.effects.moment_knm)} kNm; "
            f"VEd = {n(case.result.effects.shear_kn)} kN; "
            f"TEd = {n(case.result.effects.torsion_knm)} kNm.",
            f"{n(case.result.effects.moment_knm)} kNm"))
        rows.append(row("BS 5400 scope", "Combinations 1-3 ULS/SLS are checked for "
                        "HA, HB and HA+HB. Secondary and accidental actions in "
                        "combinations 4-5 are outside this focused model.", "Scoped"))
    sections = [sheet(2, "Analysis, loading and combinations", result.project.name, rows)]
    girder = summary.governing_moment.girder
    stages = [s for s in result.construction.stages if s.girder_index == girder]
    distributed = tuple(DistributedLoadSegment(load.magnitude_kn_m, load.x_start_m,
                         load.x_end_m, label=load.source)
                        for stage in stages for load in stage.loads)
    points = tuple(PointLoadSegment(load.magnitude_kn, load.x_m, label=load.source)
                   for stage in stages for load in stage.point_loads)
    response = simple_span_mixed_load_response(
        float(result.project.geometry.span_m), distributed, points)
    diagram_rows = []
    for label, values, unit in (("Bending moment", response.moments_knm, "kNm"),
                                ("Shear force", response.shears_kn, "kN")):
        uri = response_chart(response.stations_m, values,
                             title=f"Girder {girder} cumulative permanent {label}", unit=unit)
        diagram_rows.append(row("Construction stages",
            f"<img src='{uri}' width='600' height='160'><br>"
            "Summed permanent-stage simple-span station response; traffic is "
            "not superposed in this diagram. "
            f"Left/right reactions = {n(response.reaction_left_kn)} / "
            f"{n(response.reaction_right_kn)} kN.",
            f"Maximum magnitude {n(max(abs(v) for v in values))} {unit}", diagram=True))
    search = result.lm1 if result.lm1 is not None else result.bs_traffic.ha_hb
    stations = search.station_moments[girder - 1].stations
    if len(stations) >= 2:
        xs = tuple(s.x_m for s in stations)
        values = tuple(s.moment_knm.value for s in stations)
        uri = response_chart(xs, values,
                             title=f"Girder {girder} nominal traffic |M| envelope",
                             unit="kNm")
        diagram_rows.append(row("Traffic grillage",
            f"<img src='{uri}' width='600' height='160'><br>"
            "Absolute station envelope: neighboring points can be governed by "
            "different placements. This is not a signed single-case or factored "
            "combined-action bending diagram.",
            f"Maximum {n(max(values))} kNm", diagram=True))
    sections.append(sheet(3, "Bending moment and shear force diagrams",
                          result.project.name, diagram_rows))
    return "".join(sections)


def design_sheets(result, settings, inputs) -> str:
    eurocode = settings.code_profile is GuiCodeProfile.BS_EN
    designs = result.eurocode_design if eurocode else result.bs5400_design
    if designs is None:
        return sheet(4, "Design checks", result.project.name, [row(
            "Design", "Code-specific design was disabled for this run. "
            "No resistance or serviceability pass is asserted.", "Not assessed")])
    project = result.project
    area = project.provided_longitudinal_reinforcement.total_area_mm2
    d = inputs.effective_depth_m
    fyk = float(project.materials.fyk_mpa)
    section = project.geometry.girder_profile
    bw = float(section.width_m if hasattr(section, "width_m") else section.web_width_m)
    sections = []
    for index, design in enumerate(designs, start=1):
        rows = []
        reference = "BS EN 1992-2" if eurocode else "BS 5400-4:1990"
        if eurocode:
            steel_factor = 1 / 1.15
            concrete_factor = inputs.ec2_alpha_cc / 1.5
            concrete_strength = float(project.materials.fck_mpa)
            uls_name = design.uls_combination_name
            c = result.eurocode_combinations[index - 1].combinations
            sls = next(x for x in (c.characteristic_sls, c.frequent_sls,
                                   c.quasi_permanent_sls)
                       if x.name == design.sls_combination_name)
            rows.append(row("BS EN 1990 SLS",
                f"{escape(sls.name)}: service moment = "
                f"{n(sls.effects.moment_knm)} kNm. Distinct frequent "
                "TS/UDL factors use a separately searched weighted traffic basis.",
                f"{n(sls.effects.moment_knm)} kNm"))
        else:
            steel_factor = .87
            concrete_factor = .40
            concrete_strength = float(project.materials.fcu_mpa)
            uls_name = design.flexure_case
            combo = result.bs5400_combinations[index - 1]
            for purpose, name, field, unit in (
                ("Flexure", design.flexure_case, "moment_knm", "kNm"),
                ("Shear", design.shear_case, "shear_kn", "kN"),
                ("Cracking", design.cracking_case, "moment_knm", "kNm"),
            ):
                case = next(x for x in combo.cases if x.result.name == name)
                terms = " + ".join(
                    f"{n(case.result.factors[cat.value])} x {n(getattr(effect, field))}"
                    for cat, effect in combo.permanent_characteristic_by_category.items())
                search = getattr(result.bs_traffic, case.traffic.value)
                component = getattr(search.girders[index - 1], field)
                rows.append(row(f"BS 5400 {purpose}",
                    f"Governing {escape(name)}: Ed = sum(gammafL,G x G) + "
                    f"gammafL,Q x Q = ({terms}) + "
                    f"{n(case.result.factors['primary_live'])} x "
                    f"{n(getattr(case.nominal_traffic, field))} = "
                    f"{n(getattr(case.result.effects, field))} {unit}. "
                    f"Nominal {case.traffic.value} case {component.case_id}, "
                    f"member {component.member_id} governs this component.",
                    f"{n(getattr(case.result.effects, field))} {unit}"))
        flex = design.flexure
        if flex is None:
            rows.append(row(reference + "\nflexure", escape(design.flexure_issue or
                             "Flexure could not be assessed."), "Not assessed"))
        else:
            ductility = (f"x/d = {n(flex.neutral_axis_ratio)}; configured limit "
                         f"{n(flex.ductility_limit_ratio)}."
                         if eurocode and flex.ductility_limit_ratio is not None else "")
            passes = flex.utilization <= 1 and getattr(flex, "ductility_passes", True) is not False
            rows.append(row(reference + "\nflexure",
                f"{escape(uls_name)}. As = {n(area)} mm2, d = {n(d)} m. "
                f"Design steel force = {n(steel_factor)} x {n(fyk)} x {n(area)} "
                f"= {n(steel_factor * fyk * area)} N; concrete block stress "
                f"= {n(concrete_factor)} x {n(concrete_strength)} = "
                f"{n(concrete_factor * concrete_strength)} MPa. "
                "Engine layered compression equilibrium gives "
                f"x = {n(flex.neutral_axis_m)} m, z = {n(flex.lever_arm_m)} m, "
                f"MR = {n(flex.resistance_knm)} kNm.<br>"
                f"Utilization = MEd/MR = {n(flex.design_moment_knm)} / "
                f"{n(flex.resistance_knm)} = {n(flex.utilization)}. {ductility}",
                "PASS" if passes else "CHECK"))
        shear = design.shear
        if eurocode:
            rows.append(row(reference + "\nmaximum web resistance",
                f"Ved = {n(shear.design_shear_kn)} kN, bw = {n(bw * 1000)} mm, "
                f"d = {n(d * 1000)} mm. k = min[1 + sqrt(200/{n(d*1000)}), 2] = "
                f"{n(shear.k)}; rho_l = min[{n(area)}/"
                f"({n(bw*1000)} x {n(d*1000)}), 0.02] = {n(shear.rho_l)}. "
                "VRd,c = max[(0.18/1.50)k(100 rho_l fck)^(1/3), "
                f"0.035 k^(3/2) sqrt(fck)] bw d/1000, fck = "
                f"{n(concrete_strength)} MPa; VRd,c = {n(shear.vrdc_kn)} kN. "
                f"VRd,max = {n(shear.vrdmax_kn)} kN; "
                f"Ved/VRd,max = {n(shear.design_shear_kn)} / "
                f"{n(shear.vrdmax_kn)} = "
                f"{n(shear.design_shear_kn/shear.vrdmax_kn)}; "
                f"required Asw/s = {n(shear.required_asw_per_s_mm2_per_m)} mm2/m. "
                f"Concrete-only: {shear.concrete_only_passes}. "
                "Required links are calculated; provided links were not specified. "
                "No complete shear reinforcement pass is asserted.",
                "WEB LIMIT PASS" if shear.web_crushing_passes else "WEB LIMIT FAIL"))
        else:
            rows.append(row(reference + "\nmaximum web resistance",
                f"Ved = {n(shear.design_shear_kn)} kN; "
                f"vEd = Ved/(bw d) = {n(shear.design_shear_kn)} x 1000 / "
                f"({n(bw*1000)} x {n(d*1000)}) = "
                f"{n(shear.design_shear_stress_mpa)} MPa. "
                f"vc = {n(shear.concrete_design_shear_stress_mpa)} MPa; "
                f"VR,c = {n(shear.concrete_resistance_kn)} kN; "
                f"VR,max = min[0.75 sqrt(fcu), 4.75] bw d/1000 = "
                f"{n(shear.maximum_resistance_kn)} kN; "
                f"Asv/s = {n(shear.governing_asv_per_s_mm2_per_m)} mm2/m. "
                "Required links are calculated; provided links were not specified. "
                "No complete shear reinforcement pass is asserted.",
                "WEB LIMIT FAIL" if shear.exceeds_maximum_shear else "WEB LIMIT PASS"))
        crack = design.cracking
        if eurocode:
            strain = crack.crack_width_mm / crack.max_crack_spacing_mm if crack.max_crack_spacing_mm else 0
            rows.append(row(reference + "\ncracking",
                f"Service steel stress = {n(crack.steel_stress_mpa)} MPa. "
                f"w = sr,max(epsilon_sm - epsilon_cm) = "
                f"{n(crack.max_crack_spacing_mm)} x {strain_value(strain)} = "
                f"{n(crack.crack_width_mm)} mm; limit = {n(crack.crack_limit_mm)} mm; "
                f"utilization = {n(crack.utilization)}. "
                + ("Uncracked branch." if crack.max_crack_spacing_mm == 0
                   else "Cracked branch."),
                "PASS" if crack.utilization <= 1 else "CHECK"))
        else:
            h = float(project.geometry.total_structural_depth_m) * 1000
            denominator = 1 + 2*(crack.acr_mm-inputs.bs_nominal_cover_mm)/(h-crack.compression_depth_mm)
            rows.append(row(reference + "\ncracking",
                f"{escape(design.cracking_case)}. acr = {n(crack.acr_mm)} mm; "
                f"epsilon_m = {strain_value(crack.mean_strain)}; h = {n(h)} mm; "
                f"x = {n(crack.compression_depth_mm)} mm; "
                f"cmin = {n(inputs.bs_nominal_cover_mm)} mm.<br>"
                "w = 3 acr epsilon_m/[1 + 2(acr-cmin)/(h-x)] = "
                f"3 x {n(crack.acr_mm)} x {strain_value(crack.mean_strain)} / "
                f"{n(denominator)} = {n(crack.crack_width_mm)} mm; "
                f"limit = {n(crack.allowable_crack_width_mm)} mm.",
                "PASS" if crack.passes else "CHECK"))
        delta = design.deflection
        criterion = (f"Limit = {n(delta.allowable_deflection_mm)} mm, "
                     f"utilization = {n(delta.utilization)}; "
                     f"basis: {escape(delta.criterion_basis or '')}."
                     if delta.allowable_deflection_mm is not None else
                     "No project limit supplied; no pass/fail asserted.")
        rows.append(row(reference + "\ndeflection",
            f"{escape(delta.status)}<br>delta = deltaG + psiQ deltaQ = "
            f"{n(delta.permanent_deflection_mm)} + {n(delta.traffic_factor)} x "
            f"{n(delta.traffic_characteristic_deflection_mm)} = "
            f"{n(delta.total_deflection_mm)} mm. {criterion}",
            "Not assessed" if delta.passes is None else
            "PASS" if delta.passes else "CHECK"))
        sections.append(sheet(index + 3, f"Girder {index} design checks", project.name, rows))
    return "".join(sections)
