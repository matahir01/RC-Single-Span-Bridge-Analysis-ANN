from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise


@dataclass(frozen=True)
class SimpleSpanResult:
    reaction_left_kn: float
    reaction_right_kn: float
    max_moment_knm: float
    max_shear_kn: float


@dataclass(frozen=True)
class DistributedLoadSegment:
    magnitude_kn_m: float
    start_m: float
    end_m: float
    label: str = "distributed load"

    def __post_init__(self) -> None:
        if self.magnitude_kn_m < 0.0:
            raise ValueError("Distributed-load magnitude cannot be negative.")
        if self.start_m < 0.0 or self.end_m <= self.start_m:
            raise ValueError("Distributed-load bounds must define a positive length.")
        if not self.label.strip():
            raise ValueError("Distributed-load label cannot be empty.")

    @property
    def total_load_kn(self) -> float:
        return self.magnitude_kn_m * (self.end_m - self.start_m)

    @property
    def centroid_m(self) -> float:
        return 0.5 * (self.start_m + self.end_m)


@dataclass(frozen=True)
class PointLoadSegment:
    magnitude_kn: float
    position_m: float
    label: str = "point load"

    def __post_init__(self) -> None:
        if self.magnitude_kn < 0.0:
            raise ValueError("Point-load magnitude cannot be negative.")
        if self.position_m < 0.0:
            raise ValueError("Point-load position cannot be negative.")
        if not self.label.strip():
            raise ValueError("Point-load label cannot be empty.")


@dataclass(frozen=True)
class SimpleSpanDistributedResult:
    reaction_left_kn: float
    reaction_right_kn: float
    max_moment_knm: float
    max_moment_position_m: float
    max_abs_shear_kn: float
    max_abs_shear_position_m: float
    stations_m: tuple[float, ...]
    moments_knm: tuple[float, ...]
    shears_kn: tuple[float, ...]


def udl_simple_span(span_m: float, udl_kn_m: float) -> SimpleSpanResult:
    if span_m <= 0.0:
        raise ValueError("span_m must be greater than zero")
    if udl_kn_m < 0.0:
        raise ValueError("udl_kn_m cannot be negative")
    reaction = udl_kn_m * span_m / 2.0
    return SimpleSpanResult(
        reaction_left_kn=reaction,
        reaction_right_kn=reaction,
        max_moment_knm=udl_kn_m * span_m**2 / 8.0,
        max_shear_kn=reaction,
    )


def _validate_distributed_loads(
    span_m: float,
    loads: Sequence[DistributedLoadSegment],
) -> None:
    if span_m <= 0.0:
        raise ValueError("span_m must be greater than zero")
    if any(load.end_m > span_m + 1.0e-9 for load in loads):
        raise ValueError("Distributed load extends beyond the simple span.")


def simple_span_distributed_reactions(
    span_m: float,
    loads: Sequence[DistributedLoadSegment],
) -> tuple[float, float]:
    _validate_distributed_loads(span_m, loads)
    total = sum(load.total_load_kn for load in loads)
    reaction_right = sum(
        load.total_load_kn * load.centroid_m for load in loads
    ) / span_m
    return total - reaction_right, reaction_right


def simple_span_distributed_response_at_x(
    span_m: float,
    loads: Sequence[DistributedLoadSegment],
    x_m: float,
) -> tuple[float, float]:
    _validate_distributed_loads(span_m, loads)
    if not 0.0 <= x_m <= span_m:
        raise ValueError("Response coordinate lies outside the simple span.")
    reaction_left, _ = simple_span_distributed_reactions(span_m, loads)
    shear = reaction_left
    moment = reaction_left * x_m
    for load in loads:
        loaded_length = min(max(x_m - load.start_m, 0.0), load.end_m - load.start_m)
        if loaded_length <= 0.0:
            continue
        shear -= load.magnitude_kn_m * loaded_length
        loaded_centroid = load.start_m + loaded_length / 2.0
        moment -= load.magnitude_kn_m * loaded_length * (x_m - loaded_centroid)
    return moment, shear


def simple_span_distributed_load_response(
    span_m: float,
    loads: Sequence[DistributedLoadSegment],
    *,
    evaluation_stations_m: Sequence[float] = (),
) -> SimpleSpanDistributedResult:
    _validate_distributed_loads(span_m, loads)
    stations = {0.0, span_m}
    for load in loads:
        stations.update((load.start_m, min(load.end_m, span_m)))

    boundaries = sorted(stations)
    reaction_left, reaction_right = simple_span_distributed_reactions(span_m, loads)
    for left, right in pairwise(boundaries):
        midpoint = 0.5 * (left + right)
        intensity = sum(
            load.magnitude_kn_m
            for load in loads
            if load.start_m <= midpoint < load.end_m
        )
        if intensity <= 0.0:
            continue
        _, shear_left = simple_span_distributed_response_at_x(span_m, loads, left)
        root = left + shear_left / intensity
        if left < root < right:
            stations.add(root)

    for station in evaluation_stations_m:
        value = float(station)
        if not 0.0 <= value <= span_m:
            raise ValueError("Evaluation station lies outside the simple span.")
        stations.add(value)

    ordered = tuple(sorted(stations))
    responses = tuple(
        simple_span_distributed_response_at_x(span_m, loads, x_m)
        for x_m in ordered
    )
    moments = tuple(item[0] for item in responses)
    shears = tuple(item[1] for item in responses)
    moment_index = max(range(len(ordered)), key=lambda index: moments[index])
    shear_index = max(range(len(ordered)), key=lambda index: abs(shears[index]))
    max_abs_shear = max(
        abs(shears[shear_index]),
        abs(reaction_left),
        abs(reaction_right),
    )
    if abs(reaction_right) > abs(shears[shear_index]):
        shear_position = span_m
    elif abs(reaction_left) > abs(shears[shear_index]):
        shear_position = 0.0
    else:
        shear_position = ordered[shear_index]

    return SimpleSpanDistributedResult(
        reaction_left_kn=reaction_left,
        reaction_right_kn=reaction_right,
        max_moment_knm=moments[moment_index],
        max_moment_position_m=ordered[moment_index],
        max_abs_shear_kn=max_abs_shear,
        max_abs_shear_position_m=shear_position,
        stations_m=ordered,
        moments_knm=moments,
        shears_kn=shears,
    )


def _validate_point_loads(
    span_m: float,
    loads: Sequence[PointLoadSegment],
) -> None:
    if span_m <= 0.0:
        raise ValueError("span_m must be greater than zero")
    if any(load.position_m > span_m + 1.0e-9 for load in loads):
        raise ValueError("Point load lies beyond the simple span.")


def simple_span_mixed_reactions(
    span_m: float,
    distributed_loads: Sequence[DistributedLoadSegment],
    point_loads: Sequence[PointLoadSegment],
) -> tuple[float, float]:
    _validate_distributed_loads(span_m, distributed_loads)
    _validate_point_loads(span_m, point_loads)
    total = sum(load.total_load_kn for load in distributed_loads) + sum(
        load.magnitude_kn for load in point_loads
    )
    right_moment = sum(
        load.total_load_kn * load.centroid_m for load in distributed_loads
    ) + sum(load.magnitude_kn * load.position_m for load in point_loads)
    reaction_right = right_moment / span_m
    return total - reaction_right, reaction_right


def simple_span_mixed_response_at_x(
    span_m: float,
    distributed_loads: Sequence[DistributedLoadSegment],
    point_loads: Sequence[PointLoadSegment],
    x_m: float,
    *,
    include_point_at_x: bool = True,
) -> tuple[float, float]:
    _validate_distributed_loads(span_m, distributed_loads)
    _validate_point_loads(span_m, point_loads)
    if not 0.0 <= x_m <= span_m:
        raise ValueError("Response coordinate lies outside the simple span.")

    reaction_left, _ = simple_span_mixed_reactions(
        span_m,
        distributed_loads,
        point_loads,
    )
    shear = reaction_left
    moment = reaction_left * x_m

    for load in distributed_loads:
        loaded_length = min(
            max(x_m - load.start_m, 0.0),
            load.end_m - load.start_m,
        )
        if loaded_length <= 0.0:
            continue
        shear -= load.magnitude_kn_m * loaded_length
        loaded_centroid = load.start_m + loaded_length / 2.0
        moment -= load.magnitude_kn_m * loaded_length * (x_m - loaded_centroid)

    for load in point_loads:
        applies = (
            load.position_m <= x_m + 1.0e-12
            if include_point_at_x
            else load.position_m < x_m - 1.0e-12
        )
        if not applies:
            continue
        shear -= load.magnitude_kn
        moment -= load.magnitude_kn * (x_m - load.position_m)

    return moment, shear


def simple_span_mixed_load_response(
    span_m: float,
    distributed_loads: Sequence[DistributedLoadSegment],
    point_loads: Sequence[PointLoadSegment],
    *,
    evaluation_stations_m: Sequence[float] = (),
) -> SimpleSpanDistributedResult:
    _validate_distributed_loads(span_m, distributed_loads)
    _validate_point_loads(span_m, point_loads)

    stations = {0.0, span_m}
    for load in distributed_loads:
        stations.update((load.start_m, min(load.end_m, span_m)))
    for load in point_loads:
        stations.add(load.position_m)

    boundaries = sorted(stations)
    reaction_left, reaction_right = simple_span_mixed_reactions(
        span_m,
        distributed_loads,
        point_loads,
    )

    for left, right in pairwise(boundaries):
        if right <= left:
            continue
        midpoint = 0.5 * (left + right)
        intensity = sum(
            load.magnitude_kn_m
            for load in distributed_loads
            if load.start_m <= midpoint < load.end_m
        )
        if intensity <= 0.0:
            continue
        _, shear_left = simple_span_mixed_response_at_x(
            span_m,
            distributed_loads,
            point_loads,
            left,
            include_point_at_x=True,
        )
        root = left + shear_left / intensity
        if left < root < right:
            stations.add(root)

    for station in evaluation_stations_m:
        value = float(station)
        if not 0.0 <= value <= span_m:
            raise ValueError("Evaluation station lies outside the simple span.")
        stations.add(value)

    ordered = tuple(sorted(stations))
    responses = tuple(
        simple_span_mixed_response_at_x(
            span_m,
            distributed_loads,
            point_loads,
            x_m,
            include_point_at_x=True,
        )
        for x_m in ordered
    )
    moments = tuple(item[0] for item in responses)
    shears = tuple(item[1] for item in responses)
    moment_index = max(range(len(ordered)), key=lambda index: moments[index])

    shear_candidates: list[tuple[float, float]] = [
        (0.0, reaction_left),
        (span_m, -reaction_right),
    ]
    shear_candidates.extend(
        (ordered[index], shears[index])
        for index in range(len(ordered))
    )
    for load in point_loads:
        _, before = simple_span_mixed_response_at_x(
            span_m,
            distributed_loads,
            point_loads,
            load.position_m,
            include_point_at_x=False,
        )
        _, after = simple_span_mixed_response_at_x(
            span_m,
            distributed_loads,
            point_loads,
            load.position_m,
            include_point_at_x=True,
        )
        shear_candidates.extend(
            ((load.position_m, before), (load.position_m, after))
        )

    shear_position, governing_shear = max(
        shear_candidates,
        key=lambda item: abs(item[1]),
    )

    return SimpleSpanDistributedResult(
        reaction_left_kn=reaction_left,
        reaction_right_kn=reaction_right,
        max_moment_knm=moments[moment_index],
        max_moment_position_m=ordered[moment_index],
        max_abs_shear_kn=abs(governing_shear),
        max_abs_shear_position_m=shear_position,
        stations_m=ordered,
        moments_knm=moments,
        shears_kn=shears,
    )
