from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import ceil

from rc_single_span.analysis.permanent import (
    automatic_permanent_loads,
    automatic_permanent_point_loads,
)
from rc_single_span.analysis.sections import (
    ConcreteLayer,
    _profile_layers,
    final_composite_concrete_layers,
)
from rc_single_span.analysis.simple_span import (
    PointLoadSegment,
    simple_span_mixed_load_response,
    simple_span_mixed_response_at_x,
)
from rc_single_span.core.models import BridgeProject, PermanentActionStage
from rc_single_span.design.bs5400 import controlling_surface_distance_mm
from rc_single_span.design.detailing import (
    LongitudinalBarArrangement,
    longitudinal_cage_centroid_from_face_m,
)
from rc_single_span.design.fatigue import (
    ReinforcementFatigueResult,
    check_reinforcement_fatigue_stress_range,
)
from rc_single_span.design.layered import (
    effective_tension_area_mm2,
    effective_tension_depth_mm,
    layer_overlap,
)
from rc_single_span.design.longitudinal_detailing import CurtailmentPlan


class TerminationCodeProfile(str, Enum):
    EUROCODE = "eurocode"
    BS5400 = "bs5400"


@dataclass(frozen=True)
class TerminationRules:
    code_profile: TerminationCodeProfile
    tension_shift_length_m: float
    support_anchorage_length_m: float
    minimum_support_bars: int
    minimum_extension_beyond_theoretical_cutoff_m: float
    basis: str


@dataclass(frozen=True)
class TerminationZone:
    start_m: float
    end_m: float
    bars_required_from_demand: int
    bars_to_continue: int
    theoretical_cutoff_m: float | None
    design_cutoff_m: float | None


@dataclass(frozen=True)
class TerminationPlan:
    rules: TerminationRules
    zones: tuple[TerminationZone, ...]
    support_bars_left: int
    support_bars_right: int
    status: str


def ec2_tension_shift_length_m(
    *,
    lever_arm_m: float,
    cot_theta: float,
    cot_alpha: float = 0.0,
) -> float:
    """EC2 truss-model tension shift a_l = z(cot(theta)-cot(alpha))/2."""

    if lever_arm_m <= 0.0 or cot_theta <= 0.0 or cot_alpha < 0.0:
        raise ValueError("EC2 tension-shift inputs are invalid.")
    return max(0.0, 0.5 * lever_arm_m * (cot_theta - cot_alpha))


def build_termination_rules(
    *,
    code_profile: TerminationCodeProfile,
    support_anchorage_length_m: float,
    minimum_support_bars: int,
    minimum_extension_beyond_theoretical_cutoff_m: float,
    lever_arm_m: float | None = None,
    cot_theta: float | None = None,
    cot_alpha: float = 0.0,
    explicit_tension_shift_length_m: float | None = None,
) -> TerminationRules:
    if (
        support_anchorage_length_m <= 0.0
        or minimum_extension_beyond_theoretical_cutoff_m < 0.0
        or minimum_support_bars < 2
    ):
        raise ValueError("Termination-rule inputs are invalid.")

    if code_profile is TerminationCodeProfile.EUROCODE:
        if lever_arm_m is None or cot_theta is None:
            raise ValueError("Eurocode termination requires lever_arm_m and cot_theta.")
        shift = ec2_tension_shift_length_m(
            lever_arm_m=lever_arm_m,
            cot_theta=cot_theta,
            cot_alpha=cot_alpha,
        )
        basis = (
            "Eurocode truss-model tension shift a_l=z(cot(theta)-cot(alpha))/2; "
            "support anchorage and minimum continuation are explicit detailing inputs."
        )
    else:
        if explicit_tension_shift_length_m is None:
            raise ValueError(
                "BS 5400 termination requires an explicit verified tension-shift "
                "length; the program does not invent a legacy-code value."
            )
        if explicit_tension_shift_length_m < 0.0:
            raise ValueError("explicit_tension_shift_length_m cannot be negative.")
        shift = explicit_tension_shift_length_m
        basis = (
            "BS 5400 termination uses an explicitly supplied verified tension-shift "
            "length plus explicit support anchorage and continuation requirements."
        )

    return TerminationRules(
        code_profile=code_profile,
        tension_shift_length_m=shift,
        support_anchorage_length_m=support_anchorage_length_m,
        minimum_support_bars=minimum_support_bars,
        minimum_extension_beyond_theoretical_cutoff_m=(
            minimum_extension_beyond_theoretical_cutoff_m
        ),
        basis=basis,
    )


def apply_support_and_termination_rules(
    *,
    span_m: float,
    preliminary: CurtailmentPlan,
    rules: TerminationRules,
) -> TerminationPlan:
    if span_m <= 0.0:
        raise ValueError("span_m must be positive.")
    if rules.minimum_support_bars > preliminary.total_bars:
        raise ValueError("Minimum support bars exceed the available longitudinal bars.")

    extension = max(
        rules.tension_shift_length_m,
        rules.minimum_extension_beyond_theoretical_cutoff_m,
    )
    zones: list[TerminationZone] = []
    for zone in preliminary.zones:
        design_cutoff = None
        bars_continue = max(zone.bars_to_continue, rules.minimum_support_bars)
        if zone.theoretical_cutoff_m is not None:
            x = zone.theoretical_cutoff_m
            if x <= span_m / 2.0:
                design_cutoff = max(
                    0.0,
                    x - extension - rules.support_anchorage_length_m,
                )
            else:
                design_cutoff = min(
                    span_m,
                    x + extension + rules.support_anchorage_length_m,
                )
        zones.append(
            TerminationZone(
                start_m=zone.start_m,
                end_m=zone.end_m,
                bars_required_from_demand=zone.minimum_bars_required,
                bars_to_continue=bars_continue,
                theoretical_cutoff_m=zone.theoretical_cutoff_m,
                design_cutoff_m=design_cutoff,
            )
        )

    return TerminationPlan(
        rules=rules,
        zones=tuple(zones),
        support_bars_left=rules.minimum_support_bars,
        support_bars_right=rules.minimum_support_bars,
        status=(
            "Support anchorage, tension shift and minimum termination extension "
            "have been applied to the station-demand curtailment plan."
        ),
    )


@dataclass(frozen=True)
class FatigueVehicle:
    axle_loads_kn: tuple[float, ...]
    axle_spacings_m: tuple[float, ...]
    name: str
    provenance: str

    @property
    def axle_offsets_m(self) -> tuple[float, ...]:
        offsets = [0.0]
        for spacing in self.axle_spacings_m:
            offsets.append(offsets[-1] + spacing)
        return tuple(offsets)


def eurocode_flm3_vehicle() -> FatigueVehicle:
    return FatigueVehicle(
        axle_loads_kn=(120.0, 120.0, 120.0, 120.0),
        axle_spacings_m=(1.2, 6.0, 1.2),
        name="EN 1991-2 Fatigue Load Model 3",
        provenance=(
            "Configured FLM3 axle train: four 120 kN axles with 1.2/6.0/1.2 m "
            "longitudinal spacings. Project/National-Annex fatigue factors remain explicit."
        ),
    )


@dataclass(frozen=True)
class FatigueTrafficStressRangeResult:
    vehicle: FatigueVehicle
    station_m: float
    girder_distribution_factor: float
    maximum_vehicle_moment_knm: float
    minimum_vehicle_moment_knm: float
    maximum_steel_stress_mpa: float
    minimum_steel_stress_mpa: float
    equivalent_stress_range_mpa: float
    vehicle_front_at_max_m: float
    fatigue_check: ReinforcementFatigueResult


def _cracked_double_section(
    *,
    layers: tuple[ConcreteLayer, ...],
    tension_area_mm2: float,
    tension_depth_m: float,
    compression_area_mm2: float,
    compression_depth_m: float,
    modular_ratio: float,
    moment_knm: float,
) -> tuple[float, float, float, float]:
    if min(
        tension_area_mm2,
        tension_depth_m,
        compression_area_mm2,
        compression_depth_m,
        modular_ratio,
    ) <= 0.0 or moment_knm < 0.0:
        raise ValueError("Doubly reinforced SLS inputs are invalid.")
    if compression_depth_m >= tension_depth_m:
        raise ValueError("Compression steel must lie above tension steel.")

    d_t = tension_depth_m * 1000.0
    d_c = compression_depth_m * 1000.0
    n_as_t = modular_ratio * tension_area_mm2
    n_as_c = modular_ratio * compression_area_mm2

    def first_moment(x_mm: float) -> float:
        x_m = x_mm / 1000.0
        concrete = 0.0
        for layer in layers:
            overlap = layer_overlap(layer, top_m=0.0, bottom_m=x_m)
            if overlap is None:
                continue
            area_m2, centroid_m, _ = overlap
            concrete += area_m2 * 1.0e6 * (x_mm - centroid_m * 1000.0)
        return (
            concrete
            + n_as_c * (x_mm - d_c)
            - n_as_t * (d_t - x_mm)
        )

    low = max(d_c + 1.0e-6, 1.0e-6)
    high = d_t - 1.0e-6
    f_low = first_moment(low)
    f_high = first_moment(high)
    if f_low * f_high > 0.0:
        raise ValueError("Unable to bracket doubly reinforced cracked neutral axis.")
    for _ in range(120):
        mid = 0.5 * (low + high)
        f_mid = first_moment(mid)
        if f_low * f_mid <= 0.0:
            high = mid
        else:
            low = mid
            f_low = f_mid
    x_mm = 0.5 * (low + high)
    x_m = x_mm / 1000.0

    inertia = n_as_t * (d_t - x_mm) ** 2 + n_as_c * (x_mm - d_c) ** 2
    for layer in layers:
        top = max(layer.top_m, 0.0)
        bottom = min(layer.bottom_m, x_m)
        if bottom <= top:
            continue
        area_m2, centroid_m, _, iy_m4, _ = layer.segment_properties(
            top_m=top,
            bottom_m=bottom,
        )
        area_mm2 = area_m2 * 1.0e6
        centroid_mm = centroid_m * 1000.0
        inertia += iy_m4 * 1.0e12 + area_mm2 * (x_mm - centroid_mm) ** 2

    if inertia <= 0.0:
        raise ValueError("Doubly reinforced cracked inertia is non-positive.")
    sigma_t = modular_ratio * moment_knm * 1.0e6 * (d_t - x_mm) / inertia
    sigma_c = modular_ratio * moment_knm * 1.0e6 * (x_mm - d_c) / inertia
    return x_mm, inertia, sigma_t, sigma_c


def fatigue_vehicle_to_steel_stress_range(
    *,
    span_m: float,
    station_m: float,
    vehicle: FatigueVehicle,
    girder_distribution_factor: float,
    layers: tuple[ConcreteLayer, ...],
    tension_steel_area_mm2: float,
    tension_steel_depth_m: float,
    es_mpa: float,
    ecm_mpa: float,
    characteristic_resistance_range_mpa: float,
    step_m: float = 0.25,
    gamma_fatigue_action: float = 1.0,
    gamma_fatigue_resistance: float = 1.15,
    resistance_modifier: float = 1.0,
) -> FatigueTrafficStressRangeResult:
    """Move an explicit fatigue axle train and convert moment range to steel stress range."""

    if not 0.0 <= station_m <= span_m:
        raise ValueError("Fatigue station lies outside the span.")
    if not 0.0 < girder_distribution_factor <= 1.0:
        raise ValueError("girder_distribution_factor must lie in (0, 1].")
    if step_m <= 0.0 or min(es_mpa, ecm_mpa) <= 0.0:
        raise ValueError("Fatigue sweep inputs must be positive.")
    if len(vehicle.axle_loads_kn) != len(vehicle.axle_offsets_m):
        raise ValueError("Fatigue vehicle axle loads and spacings are inconsistent.")

    offsets = vehicle.axle_offsets_m
    front = -offsets[-1]
    maximum = -1.0
    minimum = float("inf")
    at_max = front
    moments: list[float] = []
    while front <= span_m + 1.0e-9:
        loads = []
        for load, offset in zip(vehicle.axle_loads_kn, offsets, strict=True):
            x = front + offset
            if 0.0 <= x <= span_m:
                loads.append(
                    PointLoadSegment(
                        magnitude_kn=load * girder_distribution_factor,
                        position_m=x,
                        label=vehicle.name,
                    )
                )
        moment, _ = simple_span_mixed_response_at_x(
            span_m,
            (),
            tuple(loads),
            station_m,
        )
        moments.append(moment)
        if moment > maximum:
            maximum = moment
            at_max = front
        minimum = min(minimum, moment)
        front += step_m

    minimum = max(minimum, 0.0)
    modular_ratio = es_mpa / ecm_mpa
    # Fatigue action is a stress range on the already-cracked final section.
    from rc_single_span.design.layered import cracked_layered_section

    max_section = cracked_layered_section(
        layers=layers,
        steel_area_mm2=tension_steel_area_mm2,
        steel_depth_m=tension_steel_depth_m,
        modular_ratio=modular_ratio,
        service_moment_knm=max(maximum, 0.0),
    )
    min_stress = 0.0
    if minimum > 1.0e-12:
        min_section = cracked_layered_section(
            layers=layers,
            steel_area_mm2=tension_steel_area_mm2,
            steel_depth_m=tension_steel_depth_m,
            modular_ratio=modular_ratio,
            service_moment_knm=minimum,
        )
        min_stress = min_section.steel_stress_mpa
    stress_range = max_section.steel_stress_mpa - min_stress
    fatigue = check_reinforcement_fatigue_stress_range(
        equivalent_stress_range_mpa=stress_range,
        characteristic_resistance_range_mpa=characteristic_resistance_range_mpa,
        gamma_fatigue_action=gamma_fatigue_action,
        gamma_fatigue_resistance=gamma_fatigue_resistance,
        resistance_modifier=resistance_modifier,
        provenance=(
            f"{vehicle.provenance} Longitudinal moving-axle sweep at x={station_m:.3f} m; "
            f"girder distribution factor={girder_distribution_factor:.5g}; "
            "stress range from cracked transformed section."
        ),
    )
    return FatigueTrafficStressRangeResult(
        vehicle=vehicle,
        station_m=station_m,
        girder_distribution_factor=girder_distribution_factor,
        maximum_vehicle_moment_knm=maximum,
        minimum_vehicle_moment_knm=minimum,
        maximum_steel_stress_mpa=max_section.steel_stress_mpa,
        minimum_steel_stress_mpa=min_stress,
        equivalent_stress_range_mpa=stress_range,
        vehicle_front_at_max_m=at_max,
        fatigue_check=fatigue,
    )


@dataclass(frozen=True)
class ConstructionStageSteelStress:
    stage: PermanentActionStage
    cumulative_moment_knm: float
    steel_depth_m: float
    steel_stress_mpa: float
    allowable_stress_mpa: float
    utilization: float
    passes: bool
    basis: str


def _stage_order(stage: PermanentActionStage) -> int:
    return {
        PermanentActionStage.PRECAST_GIRDER: 0,
        PermanentActionStage.DECK_CONSTRUCTION: 1,
        PermanentActionStage.SUPERIMPOSED: 2,
    }[stage]


def _construction_stage_layers(
    project: BridgeProject,
    *,
    girder_index: int,
    stage: PermanentActionStage,
) -> tuple[ConcreteLayer, ...]:
    geometry = project.geometry
    if stage is PermanentActionStage.PRECAST_GIRDER:
        return _profile_layers(geometry.girder_profile, top_m=0.0)
    if stage is PermanentActionStage.DECK_CONSTRUCTION:
        if geometry.deck.false_slab_composite_participation:
            false_depth = float(geometry.deck.precast_false_slab_depth_m)
            from rc_single_span.analysis.sections import girder_tributary_widths_m

            width = girder_tributary_widths_m(geometry)[girder_index - 1]
            return (
                ConcreteLayer(width, 0.0, false_depth, "participating false slab"),
                *_profile_layers(geometry.girder_profile, top_m=false_depth),
            )
        return _profile_layers(geometry.girder_profile, top_m=0.0)
    return final_composite_concrete_layers(geometry, girder_index=girder_index)


def construction_stage_reinforcement_stress_checks(
    project: BridgeProject,
    *,
    girder_index: int,
    arrangement: LongitudinalBarArrangement,
    cover_mm: float,
    link_diameter_mm: float,
    es_mpa: float,
    ecm_mpa: float,
    allowable_stress_mpa: float,
) -> tuple[ConstructionStageSteelStress, ...]:
    """Check cumulative permanent-load steel stress at each load-time stage."""

    if not 1 <= girder_index <= int(project.geometry.girder_count):
        raise IndexError("girder_index is outside the bridge layout.")
    if min(cover_mm, link_diameter_mm, es_mpa, ecm_mpa, allowable_stress_mpa) <= 0.0:
        raise ValueError("Construction-stage stress inputs must be positive.")

    distributed = automatic_permanent_loads(project)
    points = automatic_permanent_point_loads(project)
    centroid_from_bottom = longitudinal_cage_centroid_from_face_m(
        arrangement,
        cover_mm=cover_mm,
        link_diameter_mm=link_diameter_mm,
    )
    results = []
    for stage in PermanentActionStage:
        active_distributed = tuple(
            item
            for item in distributed
            if item.girder_index == girder_index
            and _stage_order(item.stage) <= _stage_order(stage)
        )
        active_points = tuple(
            item
            for item in points
            if item.girder_index == girder_index
            and _stage_order(item.stage) <= _stage_order(stage)
        )
        from rc_single_span.analysis.simple_span import DistributedLoadSegment

        response = simple_span_mixed_load_response(
            float(project.geometry.span_m),
            tuple(
                DistributedLoadSegment(
                    magnitude_kn_m=item.magnitude_kn_m,
                    start_m=item.x_start_m,
                    end_m=item.x_end_m,
                    label=item.source,
                )
                for item in active_distributed
            ),
            tuple(
                PointLoadSegment(
                    magnitude_kn=item.magnitude_kn,
                    position_m=item.x_m,
                    label=item.source,
                )
                for item in active_points
            ),
        )
        layers = _construction_stage_layers(
            project,
            girder_index=girder_index,
            stage=stage,
        )
        stage_depth = max(item.bottom_m for item in layers)
        steel_depth = stage_depth - centroid_from_bottom
        if steel_depth <= 0.0:
            raise ValueError("Longitudinal cage lies outside a construction-stage section.")
        from rc_single_span.design.layered import cracked_layered_section

        cracked = cracked_layered_section(
            layers=layers,
            steel_area_mm2=arrangement.provided_area_mm2,
            steel_depth_m=steel_depth,
            modular_ratio=es_mpa / ecm_mpa,
            service_moment_knm=response.max_moment_knm,
        )
        utilization = cracked.steel_stress_mpa / allowable_stress_mpa
        results.append(
            ConstructionStageSteelStress(
                stage=stage,
                cumulative_moment_knm=response.max_moment_knm,
                steel_depth_m=steel_depth,
                steel_stress_mpa=cracked.steel_stress_mpa,
                allowable_stress_mpa=allowable_stress_mpa,
                utilization=utilization,
                passes=utilization <= 1.0 + 1.0e-12,
                basis=(
                    "Cumulative permanent actions up to the load-time stage, "
                    "checked on that stage's participating concrete section using "
                    "a cracked transformed-section steel stress."
                ),
            )
        )
    return tuple(results)


@dataclass(frozen=True)
class LapSpliceZone:
    start_m: float
    end_m: float
    lap_length_m: float
    maximum_bars_spliced_together: int
    stagger_groups: int
    demand_ratio: float
    permitted: bool


def build_lap_splice_zones(
    *,
    span_m: float,
    termination: TerminationPlan,
    lap_length_m: float,
    end_exclusion_m: float,
    maximum_splice_fraction: float = 0.50,
    maximum_demand_ratio_for_splicing: float = 0.70,
) -> tuple[LapSpliceZone, ...]:
    if (
        span_m <= 0.0
        or lap_length_m <= 0.0
        or end_exclusion_m < 0.0
        or not 0.0 < maximum_splice_fraction <= 1.0
        or not 0.0 < maximum_demand_ratio_for_splicing <= 1.0
    ):
        raise ValueError("Lap/splice zoning inputs are invalid.")

    total = max(zone.bars_to_continue for zone in termination.zones)
    max_together = max(1, int(total * maximum_splice_fraction))
    groups = ceil(total / max_together)
    result = []
    for zone in termination.zones:
        demand_ratio = zone.bars_required_from_demand / max(total, 1)
        enough_length = zone.end_m - zone.start_m >= lap_length_m
        away_from_ends = (
            zone.start_m >= end_exclusion_m
            and zone.end_m <= span_m - end_exclusion_m
        )
        permitted = (
            enough_length
            and away_from_ends
            and demand_ratio <= maximum_demand_ratio_for_splicing + 1.0e-12
        )
        result.append(
            LapSpliceZone(
                start_m=zone.start_m,
                end_m=zone.end_m,
                lap_length_m=lap_length_m,
                maximum_bars_spliced_together=max_together,
                stagger_groups=groups,
                demand_ratio=demand_ratio,
                permitted=permitted,
            )
        )
    return tuple(result)


@dataclass(frozen=True)
class EndZoneCongestionResult:
    bearing_pressure_mpa: float
    allowable_bearing_pressure_mpa: float
    bearing_pressure_passes: bool
    clear_width_per_bar_mm: float
    minimum_clear_spacing_mm: float
    bar_spacing_passes: bool
    link_spacing_mm: float
    maximum_link_spacing_mm: float
    link_spacing_passes: bool
    longitudinal_steel_ratio: float
    maximum_local_steel_ratio: float
    congestion_passes: bool
    passes: bool


def check_local_bearing_end_zone_congestion(
    *,
    support_reaction_kn: float,
    bearing_width_mm: float,
    bearing_length_mm: float,
    allowable_bearing_pressure_mpa: float,
    end_zone_width_mm: float,
    end_zone_depth_mm: float,
    longitudinal_bar_count: int,
    longitudinal_bar_diameter_mm: float,
    cover_mm: float,
    link_diameter_mm: float,
    link_spacing_mm: float,
    maximum_link_spacing_mm: float,
    minimum_clear_spacing_mm: float,
    maximum_local_steel_ratio: float = 0.08,
) -> EndZoneCongestionResult:
    positive = (
        support_reaction_kn,
        bearing_width_mm,
        bearing_length_mm,
        allowable_bearing_pressure_mpa,
        end_zone_width_mm,
        end_zone_depth_mm,
        longitudinal_bar_diameter_mm,
        cover_mm,
        link_diameter_mm,
        link_spacing_mm,
        maximum_link_spacing_mm,
        minimum_clear_spacing_mm,
        maximum_local_steel_ratio,
    )
    if any(value <= 0.0 for value in positive) or longitudinal_bar_count < 2:
        raise ValueError("End-zone congestion inputs are invalid.")

    bearing_pressure = (
        support_reaction_kn * 1000.0 / (bearing_width_mm * bearing_length_mm)
    )
    inner_width = end_zone_width_mm - 2.0 * (cover_mm + link_diameter_mm)
    clear = (
        inner_width - longitudinal_bar_count * longitudinal_bar_diameter_mm
    ) / (longitudinal_bar_count - 1)
    steel_area = (
        longitudinal_bar_count
        * 3.141592653589793
        * longitudinal_bar_diameter_mm**2
        / 4.0
    )
    zone_area = end_zone_width_mm * end_zone_depth_mm
    rho = steel_area / zone_area
    bearing_ok = bearing_pressure <= allowable_bearing_pressure_mpa + 1.0e-12
    spacing_ok = clear >= minimum_clear_spacing_mm - 1.0e-12
    links_ok = link_spacing_mm <= maximum_link_spacing_mm + 1.0e-12
    congestion_ok = rho <= maximum_local_steel_ratio + 1.0e-12
    return EndZoneCongestionResult(
        bearing_pressure_mpa=bearing_pressure,
        allowable_bearing_pressure_mpa=allowable_bearing_pressure_mpa,
        bearing_pressure_passes=bearing_ok,
        clear_width_per_bar_mm=clear,
        minimum_clear_spacing_mm=minimum_clear_spacing_mm,
        bar_spacing_passes=spacing_ok,
        link_spacing_mm=link_spacing_mm,
        maximum_link_spacing_mm=maximum_link_spacing_mm,
        link_spacing_passes=links_ok,
        longitudinal_steel_ratio=rho,
        maximum_local_steel_ratio=maximum_local_steel_ratio,
        congestion_passes=congestion_ok,
        passes=bearing_ok and spacing_ok and links_ok and congestion_ok,
    )


@dataclass(frozen=True)
class DoublyReinforcedSLSResult:
    neutral_axis_mm: float
    second_moment_mm4: float
    tension_steel_stress_mpa: float
    compression_steel_stress_mpa: float
    tension_stress_limit_mpa: float
    compression_stress_limit_mpa: float
    tension_stress_passes: bool
    compression_stress_passes: bool
    crack_width_mm: float | None
    crack_limit_mm: float | None
    crack_passes: bool | None
    passes: bool
    basis: str


def check_doubly_reinforced_sls_ec2(
    *,
    layers: tuple[ConcreteLayer, ...],
    total_depth_m: float,
    service_moment_knm: float,
    tension: LongitudinalBarArrangement,
    compression: LongitudinalBarArrangement,
    tension_depth_m: float,
    compression_depth_m: float,
    cover_mm: float,
    es_mpa: float,
    ecm_mpa: float,
    fct_eff_mpa: float,
    crack_limit_mm: float,
    tension_stress_limit_mpa: float,
    compression_stress_limit_mpa: float,
    kt: float = 0.4,
) -> DoublyReinforcedSLSResult:
    x_mm, inertia, sigma_t, sigma_c = _cracked_double_section(
        layers=layers,
        tension_area_mm2=tension.provided_area_mm2,
        tension_depth_m=tension_depth_m,
        compression_area_mm2=compression.provided_area_mm2,
        compression_depth_m=compression_depth_m,
        modular_ratio=es_mpa / ecm_mpa,
        moment_knm=service_moment_knm,
    )
    hceff = effective_tension_depth_mm(
        total_depth_m=total_depth_m,
        steel_depth_m=tension_depth_m,
        neutral_axis_from_top_mm=x_mm,
    )
    aceff = effective_tension_area_mm2(
        layers=layers,
        total_depth_m=total_depth_m,
        effective_tension_depth_mm_value=hceff,
    )
    rho = tension.provided_area_mm2 / aceff
    spacing = tension.bar_diameter_mm + tension.clear_horizontal_spacing_mm
    strain_calc = (
        sigma_t
        - kt * fct_eff_mpa / rho * (1.0 + es_mpa / ecm_mpa * rho)
    ) / es_mpa
    strain_min = 0.6 * sigma_t / es_mpa
    strain_difference = max(strain_calc, strain_min, 0.0)
    close_spacing = spacing <= 5.0 * (cover_mm + tension.bar_diameter_mm / 2.0)
    srmax = (
        3.4 * cover_mm
        + 0.8 * 0.5 * 0.425 * tension.bar_diameter_mm / rho
        if close_spacing
        else 1.3 * (total_depth_m * 1000.0 - x_mm)
    )
    crack = srmax * strain_difference
    tension_ok = sigma_t <= tension_stress_limit_mpa + 1.0e-12
    compression_ok = sigma_c <= compression_stress_limit_mpa + 1.0e-12
    crack_ok = crack <= crack_limit_mm + 1.0e-12
    return DoublyReinforcedSLSResult(
        neutral_axis_mm=x_mm,
        second_moment_mm4=inertia,
        tension_steel_stress_mpa=sigma_t,
        compression_steel_stress_mpa=sigma_c,
        tension_stress_limit_mpa=tension_stress_limit_mpa,
        compression_stress_limit_mpa=compression_stress_limit_mpa,
        tension_stress_passes=tension_ok,
        compression_stress_passes=compression_ok,
        crack_width_mm=crack,
        crack_limit_mm=crack_limit_mm,
        crack_passes=crack_ok,
        passes=tension_ok and compression_ok and crack_ok,
        basis=(
            "Doubly reinforced cracked transformed section with both steel cages "
            "included in neutral-axis/inertia solution; EC2 crack spacing/strain "
            "framework evaluated using the resulting tension-steel stress."
        ),
    )


def check_doubly_reinforced_sls_bs5400(
    *,
    layers: tuple[ConcreteLayer, ...],
    total_depth_m: float,
    permanent_moment_knm: float,
    live_moment_knm: float,
    tension: LongitudinalBarArrangement,
    compression: LongitudinalBarArrangement,
    tension_depth_m: float,
    compression_depth_m: float,
    cover_mm: float,
    es_mpa: float,
    ec_modified_mpa: float,
    tension_zone_width_m: float,
    crack_point_depth_mm: float,
    allowable_crack_width_mm: float,
    tension_stress_limit_mpa: float,
    compression_stress_limit_mpa: float,
) -> DoublyReinforcedSLSResult:
    service_moment = permanent_moment_knm + live_moment_knm
    x_mm, inertia, sigma_t, sigma_c = _cracked_double_section(
        layers=layers,
        tension_area_mm2=tension.provided_area_mm2,
        tension_depth_m=tension_depth_m,
        compression_area_mm2=compression.provided_area_mm2,
        compression_depth_m=compression_depth_m,
        modular_ratio=es_mpa / ec_modified_mpa,
        moment_knm=service_moment,
    )
    h_mm = total_depth_m * 1000.0
    d_mm = tension_depth_m * 1000.0
    if not x_mm <= crack_point_depth_mm <= h_mm:
        raise ValueError("crack_point_depth_mm must lie in the tensile zone.")
    epsilon_s = sigma_t / es_mpa
    epsilon_1 = (
        0.0
        if epsilon_s <= 0.0
        else epsilon_s * (crack_point_depth_mm - x_mm) / (d_mm - x_mm)
    )
    # Same explicit BS mean-strain structure used in the singly reinforced path.
    h1 = h_mm - x_mm
    a_cr = tension_zone_width_m * h1
    rho = tension.provided_area_mm2 / max(a_cr, 1.0)
    tension_stiffening = min(0.55 * rho, 0.5)
    mean_strain = max(epsilon_1 * (1.0 - tension_stiffening), 0.0)
    spacing = tension.bar_diameter_mm + tension.clear_horizontal_spacing_mm
    acr = controlling_surface_distance_mm(
        bar_spacing_mm=spacing,
        nominal_cover_to_bar_surface_mm=cover_mm,
        bar_diameter_mm=tension.bar_diameter_mm,
    )
    denominator = 1.0 + 2.0 * (acr - cover_mm) / max(h_mm - x_mm, 1.0e-9)
    crack = 0.0 if mean_strain <= 0.0 else 3.0 * acr * mean_strain / denominator
    tension_ok = sigma_t <= tension_stress_limit_mpa + 1.0e-12
    compression_ok = sigma_c <= compression_stress_limit_mpa + 1.0e-12
    crack_ok = crack <= allowable_crack_width_mm + 1.0e-12
    return DoublyReinforcedSLSResult(
        neutral_axis_mm=x_mm,
        second_moment_mm4=inertia,
        tension_steel_stress_mpa=sigma_t,
        compression_steel_stress_mpa=sigma_c,
        tension_stress_limit_mpa=tension_stress_limit_mpa,
        compression_stress_limit_mpa=compression_stress_limit_mpa,
        tension_stress_passes=tension_ok,
        compression_stress_passes=compression_ok,
        crack_width_mm=crack,
        crack_limit_mm=allowable_crack_width_mm,
        crack_passes=crack_ok,
        passes=tension_ok and compression_ok and crack_ok,
        basis=(
            "Doubly reinforced cracked transformed section including both cages; "
            "BS-style crack geometry evaluated using the resulting tension-steel stress."
        ),
    )
