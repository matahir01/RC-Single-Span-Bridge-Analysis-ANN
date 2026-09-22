from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

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
    """Symmetric concrete band with constant or linearly varying width.

    width_m is the band width at top_m. When bottom_width_m is omitted the
    band is rectangular, preserving the original API. Supplying bottom_width_m
    creates an exact symmetric trapezoidal band for physical I-girder haunches.
    """

    width_m: float
    top_m: float
    bottom_m: float
    label: str
    bottom_width_m: float | None = None

    def __post_init__(self) -> None:
        if self.width_m <= 0.0 or self.top_m < 0.0 or self.bottom_m <= self.top_m:
            raise ValueError("Concrete-layer dimensions are invalid.")
        if self.bottom_width_m is not None and self.bottom_width_m <= 0.0:
            raise ValueError("Concrete-layer bottom width must be positive.")
        if not self.label.strip():
            raise ValueError("Concrete-layer label cannot be empty.")

    @property
    def depth_m(self) -> float:
        return self.bottom_m - self.top_m

    @property
    def top_width_m(self) -> float:
        return self.width_m

    @property
    def effective_bottom_width_m(self) -> float:
        return self.width_m if self.bottom_width_m is None else self.bottom_width_m

    @property
    def is_tapered(self) -> bool:
        return abs(self.effective_bottom_width_m - self.width_m) > 1.0e-12

    def width_at_m(self, y_m: float) -> float:
        if y_m < self.top_m - 1.0e-12 or y_m > self.bottom_m + 1.0e-12:
            raise ValueError("Requested ordinate lies outside the concrete layer.")
        ratio = (y_m - self.top_m) / self.depth_m
        return self.width_m + ratio * (
            self.effective_bottom_width_m - self.width_m
        )

    def segment_properties(
        self,
        *,
        top_m: float,
        bottom_m: float,
    ) -> tuple[float, float, float, float, float]:
        """Return A, centroid, depth, Iy(cg) and Iz(cg) for an overlap segment."""

        segment_top = max(self.top_m, top_m)
        segment_bottom = min(self.bottom_m, bottom_m)
        if segment_bottom <= segment_top:
            raise ValueError("Concrete-layer segment has no positive overlap.")

        depth = segment_bottom - segment_top
        top_width = self.width_at_m(segment_top)
        bottom_width = self.width_at_m(segment_bottom)
        width_sum = top_width + bottom_width
        area = 0.5 * width_sum * depth
        local_centroid = (
            depth * (top_width + 2.0 * bottom_width) / (3.0 * width_sum)
        )
        centroid = segment_top + local_centroid

        second_about_segment_top = (
            depth**3 * (top_width + 3.0 * bottom_width) / 12.0
        )
        iy_centroid = second_about_segment_top - area * local_centroid**2
        iz_centroid = (
            depth
            * (
                top_width**3
                + top_width**2 * bottom_width
                + top_width * bottom_width**2
                + bottom_width**3
            )
            / 48.0
        )
        return area, centroid, depth, iy_centroid, iz_centroid

    @property
    def area_m2(self) -> float:
        return self.segment_properties(
            top_m=self.top_m,
            bottom_m=self.bottom_m,
        )[0]

    @property
    def centroid_from_top_m(self) -> float:
        return self.segment_properties(
            top_m=self.top_m,
            bottom_m=self.bottom_m,
        )[1]

    @property
    def centroidal_iy_m4(self) -> float:
        return self.segment_properties(
            top_m=self.top_m,
            bottom_m=self.bottom_m,
        )[3]

    @property
    def centroidal_iz_m4(self) -> float:
        return self.segment_properties(
            top_m=self.top_m,
            bottom_m=self.bottom_m,
        )[4]


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
        z2 = z1 + float(profile.top_haunch_depth_m)
        z3 = z2 + float(profile.web_depth_m)
        z4 = z3 + float(profile.bottom_haunch_depth_m)
        z5 = z4 + float(profile.bottom_flange_thickness_m)

        layers: list[ConcreteLayer] = [
            ConcreteLayer(
                float(profile.top_flange_width_m),
                top_m,
                z1,
                "precast I-girder top flange",
            )
        ]
        if profile.top_haunch_depth_m > 0.0:
            layers.append(
                ConcreteLayer(
                    float(profile.top_flange_width_m),
                    z1,
                    z2,
                    "precast I-girder top haunch",
                    bottom_width_m=float(profile.web_width_m),
                )
            )
        layers.append(
            ConcreteLayer(
                float(profile.web_width_m),
                z2,
                z3,
                "precast I-girder web",
            )
        )
        if profile.bottom_haunch_depth_m > 0.0:
            layers.append(
                ConcreteLayer(
                    float(profile.web_width_m),
                    z3,
                    z4,
                    "precast I-girder bottom haunch",
                    bottom_width_m=float(profile.bottom_flange_width_m),
                )
            )
        layers.append(
            ConcreteLayer(
                float(profile.bottom_flange_width_m),
                z4,
                z5,
                "precast I-girder bottom flange",
            )
        )
        return tuple(layers)
    raise TypeError("Unsupported girder profile.")


def _layer_torsion_constant_m4(layer: ConcreteLayer) -> float:
    """Return component torsion constant used by the grillage stiffness model.

    Rectangular bands retain the existing exact rectangle expression. For a
    tapered haunch, the mean-width rectangle is used for J; area, centroid and
    bending inertias remain exact for the trapezoid.
    """

    width = 0.5 * (layer.top_width_m + layer.effective_bottom_width_m)
    return rectangular_torsion_constant_m4(width, layer.depth_m)


def _properties(layers: tuple[ConcreteLayer, ...], *, basis: str) -> SectionProperties:
    area = sum(layer.area_m2 for layer in layers)
    centroid = sum(
        layer.area_m2 * layer.centroid_from_top_m for layer in layers
    ) / area
    iy = sum(
        layer.centroidal_iy_m4
        + layer.area_m2 * (layer.centroid_from_top_m - centroid) ** 2
        for layer in layers
    )
    iz = sum(layer.centroidal_iz_m4 for layer in layers)
    torsion = sum(_layer_torsion_constant_m4(layer) for layer in layers)
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


def final_composite_concrete_layers(
    geometry: SingleSpanBridgeGeometry,
    *,
    girder_index: int,
) -> tuple[ConcreteLayer, ...]:
    """Return the actual participating final-state concrete bands for one girder.

    Non-participating construction layers retain their physical offset through
    the girder top coordinate but contribute no concrete area. This is the
    geometry used by layered ULS/SLS design checks.
    """

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
    return tuple(layers)


def final_composite_girder_properties(
    geometry: SingleSpanBridgeGeometry,
    *,
    girder_index: int,
) -> SectionProperties:
    return _properties(
        final_composite_concrete_layers(
            geometry,
            girder_index=girder_index,
        ),
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
    if any(b <= a for a, b in pairwise(stations_m)):
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



def girder_web_width_m(geometry: SingleSpanBridgeGeometry) -> float:
    """Return the physical web width governing longitudinal shear."""

    profile = geometry.girder_profile
    if isinstance(profile, RectangularGirderProfile):
        return float(profile.width_m)
    if isinstance(profile, TGirderProfile):
        return float(profile.web_width_m)
    if isinstance(profile, IGirderProfile):
        return float(profile.web_width_m)
    raise TypeError("Unsupported girder profile.")
