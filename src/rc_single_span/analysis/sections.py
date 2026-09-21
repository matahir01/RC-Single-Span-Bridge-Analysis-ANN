from __future__ import annotations

from dataclasses import dataclass

from rc_single_span.core.models import (
    GirderProfile,
    IGirderProfile,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
    TGirderProfile,
)


@dataclass(frozen=True)
class SectionProperties:
    area_m2: float
    centroid_from_top_m: float
    iy_m4: float
    iz_m4: float
    torsion_constant_m4: float
    basis: str

    def __post_init__(self) -> None:
        if min(
            self.area_m2,
            self.iy_m4,
            self.iz_m4,
            self.torsion_constant_m4,
        ) <= 0.0:
            raise ValueError("Section area and stiffness properties must be positive.")
        if not self.basis.strip():
            raise ValueError("Section-property basis cannot be empty.")


@dataclass(frozen=True)
class ConcreteLayer:
    width_m: float
    top_m: float
    bottom_m: float
    label: str

    def __post_init__(self) -> None:
        if self.width_m <= 0.0 or self.top_m < 0.0 or self.bottom_m <= self.top_m:
            raise ValueError("Concrete-layer dimensions are invalid.")
        if not self.label.strip():
            raise ValueError("Concrete-layer label cannot be empty.")

    @property
    def depth_m(self) -> float:
        return self.bottom_m - self.top_m

    @property
    def area_m2(self) -> float:
        return self.width_m * self.depth_m

    @property
    def centroid_from_top_m(self) -> float:
        return 0.5 * (self.top_m + self.bottom_m)


def rectangular_torsion_constant_m4(width_m: float, depth_m: float) -> float:
    if width_m <= 0.0 or depth_m <= 0.0:
        raise ValueError("Rectangle dimensions must be positive.")
    long_side = max(width_m, depth_m)
    short_side = min(width_m, depth_m)
    ratio = short_side / long_side
    return long_side * short_side**3 * (
        1.0 / 3.0 - 0.21 * ratio * (1.0 - ratio**4 / 12.0)
    )


def _profile_layers(profile: GirderProfile, *, top_m: float) -> tuple[ConcreteLayer, ...]:
    if isinstance(profile, RectangularGirderProfile):
        return (
            ConcreteLayer(
                float(profile.width_m),
                top_m,
                top_m + float(profile.depth_m),
                "precast rectangular girder",
            ),
        )
    if isinstance(profile, TGirderProfile):
        flange = float(profile.flange_thickness_m)
        total = float(profile.total_depth_m)
        return (
            ConcreteLayer(
                float(profile.flange_width_m),
                top_m,
                top_m + flange,
                "precast T-girder flange",
            ),
            ConcreteLayer(
                float(profile.web_width_m),
                top_m + flange,
                top_m + total,
                "precast T-girder web",
            ),
        )
    if isinstance(profile, IGirderProfile):
        z1 = top_m + float(profile.top_flange_thickness_m)
        z2 = z1 + float(profile.web_depth_m)
        z3 = z2 + float(profile.bottom_flange_thickness_m)
        return (
            ConcreteLayer(
                float(profile.top_flange_width_m),
                top_m,
                z1,
                "precast I-girder top flange",
            ),
            ConcreteLayer(
                float(profile.web_width_m),
                z1,
                z2,
                "precast I-girder web",
            ),
            ConcreteLayer(
                float(profile.bottom_flange_width_m),
                z2,
                z3,
                "precast I-girder bottom flange",
            ),
        )
    raise TypeError("Unsupported girder profile.")


def _properties(layers: tuple[ConcreteLayer, ...], *, basis: str) -> SectionProperties:
    area = sum(layer.area_m2 for layer in layers)
    centroid = sum(
        layer.area_m2 * layer.centroid_from_top_m for layer in layers
    ) / area
    iy = sum(
        layer.width_m * layer.depth_m**3 / 12.0
        + layer.area_m2 * (layer.centroid_from_top_m - centroid) ** 2
        for layer in layers
    )
    iz = sum(layer.depth_m * layer.width_m**3 / 12.0 for layer in layers)
    torsion = sum(
        rectangular_torsion_constant_m4(layer.width_m, layer.depth_m)
        for layer in layers
    )
    return SectionProperties(area, centroid, iy, iz, torsion, basis)


def girder_y_positions_m(geometry: SingleSpanBridgeGeometry) -> tuple[float, ...]:
    half = geometry.girder_line_width_m / 2.0
    return tuple(
        -half + index * float(geometry.girder_spacing_m)
        for index in range(int(geometry.girder_count))
    )


def girder_tributary_bands_m(
    geometry: SingleSpanBridgeGeometry,
) -> tuple[tuple[float, float], ...]:
    positions = girder_y_positions_m(geometry)
    half_deck = float(geometry.deck_width_m) / 2.0
    boundaries = [-half_deck]
    boundaries.extend(
        0.5 * (positions[index] + positions[index + 1])
        for index in range(len(positions) - 1)
    )
    boundaries.append(half_deck)
    return tuple(
        (float(boundaries[index]), float(boundaries[index + 1]))
        for index in range(len(positions))
    )


def girder_tributary_widths_m(
    geometry: SingleSpanBridgeGeometry,
) -> tuple[float, ...]:
    return tuple(right - left for left, right in girder_tributary_bands_m(geometry))


def precast_girder_properties(geometry: SingleSpanBridgeGeometry) -> SectionProperties:
    return _properties(
        _profile_layers(geometry.girder_profile, top_m=0.0),
        basis="gross physical precast girder",
    )


def deck_construction_girder_properties(
    geometry: SingleSpanBridgeGeometry,
    *,
    girder_index: int,
) -> SectionProperties:
    if not 1 <= girder_index <= int(geometry.girder_count):
        raise ValueError("girder_index is outside the bridge layout.")
    if not geometry.deck.false_slab_composite_participation:
        return precast_girder_properties(geometry)

    width = girder_tributary_widths_m(geometry)[girder_index - 1]
    in_situ = float(geometry.deck.in_situ_slab_depth_m)
    false_depth = float(geometry.deck.precast_false_slab_depth_m)
    girder_top = float(geometry.deck.physical_depth_m)
    layers = (
        ConcreteLayer(
            width,
            in_situ,
            in_situ + false_depth,
            "construction-stage composite false slab",
        ),
        *_profile_layers(geometry.girder_profile, top_m=girder_top),
    )
    return _properties(
        layers,
        basis="precast girder plus explicitly participating false slab; wet slab excluded",
    )


def final_composite_girder_properties(
    geometry: SingleSpanBridgeGeometry,
    *,
    girder_index: int,
) -> SectionProperties:
    if not 1 <= girder_index <= int(geometry.girder_count):
        raise ValueError("girder_index is outside the bridge layout.")
    width = girder_tributary_widths_m(geometry)[girder_index - 1]
    deck = geometry.deck
    layers: list[ConcreteLayer] = []
    in_situ = float(deck.in_situ_slab_depth_m)
    false_depth = float(deck.precast_false_slab_depth_m)

    if deck.in_situ_slab_composite_participation:
        layers.append(
            ConcreteLayer(width, 0.0, in_situ, "participating in-situ deck")
        )
    if deck.false_slab_composite_participation:
        layers.append(
            ConcreteLayer(
                width,
                in_situ,
                in_situ + false_depth,
                "participating precast false slab",
            )
        )
    layers.extend(
        _profile_layers(
            geometry.girder_profile,
            top_m=float(deck.physical_depth_m),
        )
    )
    return _properties(
        tuple(layers),
        basis="final composite girder with explicitly participating deck layers",
    )


def transverse_deck_strip_properties(
    geometry: SingleSpanBridgeGeometry,
    *,
    strip_width_m: float,
) -> SectionProperties:
    if strip_width_m <= 0.0:
        raise ValueError("Transverse deck strip width must be positive.")
    depth = float(geometry.deck.composite_depth_m)
    if depth <= 0.0:
        raise ValueError("Final transverse deck requires participating slab concrete.")
    return _properties(
        (
            ConcreteLayer(
                strip_width_m,
                0.0,
                depth,
                "transverse participating deck strip",
            ),
        ),
        basis="gross participating transverse deck strip",
    )


def station_tributary_widths_m(stations_m: tuple[float, ...]) -> tuple[float, ...]:
    if len(stations_m) < 2:
        raise ValueError("At least two longitudinal stations are required.")
    if any(b <= a for a, b in zip(stations_m, stations_m[1:], strict=True)):
        raise ValueError("Stations must be strictly increasing.")
    widths = []
    for index, station in enumerate(stations_m):
        if index == 0:
            width = 0.5 * (stations_m[1] - station)
        elif index == len(stations_m) - 1:
            width = 0.5 * (station - stations_m[index - 1])
        else:
            width = 0.5 * (stations_m[index + 1] - stations_m[index - 1])
        widths.append(width)
    return tuple(widths)
