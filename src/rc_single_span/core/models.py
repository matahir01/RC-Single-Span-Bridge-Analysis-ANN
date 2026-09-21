from __future__ import annotations

from enum import Enum
from math import pi
from typing import Literal

from pydantic import BaseModel, Field, PositiveFloat, PositiveInt, model_validator


class DesignStandard(str, Enum):
    EUROCODE = "eurocode"
    BS5400 = "bs5400"


class PermanentActionStage(str, Enum):
    PRECAST_GIRDER = "precast_girder"
    DECK_CONSTRUCTION = "deck_construction"
    SUPERIMPOSED = "superimposed"


class SectionType(str, Enum):
    RECTANGULAR = "rectangular"
    T = "t"
    I = "i"


class RectangularGirderProfile(BaseModel):
    shape: Literal["rectangular"] = "rectangular"
    width_m: PositiveFloat
    depth_m: PositiveFloat

    @property
    def area_m2(self) -> float:
        return float(self.width_m * self.depth_m)

    @property
    def total_depth_m(self) -> float:
        return float(self.depth_m)

    @property
    def section_type(self) -> SectionType:
        return SectionType.RECTANGULAR


class TGirderProfile(BaseModel):
    shape: Literal["t"] = "t"
    flange_width_m: PositiveFloat
    flange_thickness_m: PositiveFloat
    web_width_m: PositiveFloat
    total_depth_m: PositiveFloat

    @model_validator(mode="after")
    def validate_profile(self) -> TGirderProfile:
        if self.flange_thickness_m >= self.total_depth_m:
            raise ValueError("T-girder flange thickness must be smaller than total depth.")
        if self.web_width_m > self.flange_width_m:
            raise ValueError("T-girder web width cannot exceed flange width.")
        return self

    @property
    def area_m2(self) -> float:
        web_depth_m = float(self.total_depth_m - self.flange_thickness_m)
        return float(
            self.flange_width_m * self.flange_thickness_m
            + self.web_width_m * web_depth_m
        )

    @property
    def section_type(self) -> SectionType:
        return SectionType.T


class IGirderProfile(BaseModel):
    shape: Literal["i"] = "i"
    top_flange_width_m: PositiveFloat
    top_flange_thickness_m: PositiveFloat
    web_width_m: PositiveFloat
    web_depth_m: PositiveFloat
    bottom_flange_width_m: PositiveFloat
    bottom_flange_thickness_m: PositiveFloat

    @model_validator(mode="after")
    def validate_profile(self) -> IGirderProfile:
        if self.web_width_m > max(
            self.top_flange_width_m,
            self.bottom_flange_width_m,
        ):
            raise ValueError("I-girder web width is inconsistent with flange widths.")
        return self

    @property
    def total_depth_m(self) -> float:
        return float(
            self.top_flange_thickness_m
            + self.web_depth_m
            + self.bottom_flange_thickness_m
        )

    @property
    def area_m2(self) -> float:
        return float(
            self.top_flange_width_m * self.top_flange_thickness_m
            + self.web_width_m * self.web_depth_m
            + self.bottom_flange_width_m * self.bottom_flange_thickness_m
        )

    @property
    def section_type(self) -> SectionType:
        return SectionType.I


GirderProfile = RectangularGirderProfile | TGirderProfile | IGirderProfile


class DeckConstruction(BaseModel):
    precast_false_slab_depth_m: PositiveFloat = 0.075
    in_situ_slab_depth_m: PositiveFloat = 0.175
    false_slab_composite_participation: bool = False
    in_situ_slab_composite_participation: bool = True

    @property
    def physical_depth_m(self) -> float:
        return float(self.precast_false_slab_depth_m + self.in_situ_slab_depth_m)

    @property
    def composite_depth_m(self) -> float:
        depth = 0.0
        if self.false_slab_composite_participation:
            depth += float(self.precast_false_slab_depth_m)
        if self.in_situ_slab_composite_participation:
            depth += float(self.in_situ_slab_depth_m)
        return depth


class MaterialProperties(BaseModel):
    """Physical material data without silently translating between standards."""

    fyk_mpa: PositiveFloat
    fck_mpa: PositiveFloat | None = None
    fcu_mpa: PositiveFloat | None = None
    concrete_density_kn_m3: PositiveFloat = 24.0
    elastic_modulus_mpa: PositiveFloat | None = None

    @model_validator(mode="after")
    def require_concrete_strength(self) -> MaterialProperties:
        if self.fck_mpa is None and self.fcu_mpa is None:
            raise ValueError("At least one characteristic concrete strength is required.")
        return self

    def require_for(self, standard: DesignStandard) -> None:
        if standard is DesignStandard.EUROCODE and self.fck_mpa is None:
            raise ValueError(
                "Eurocode design requires explicit fck_mpa; no BS cube-to-cylinder "
                "conversion is performed automatically."
            )
        if standard is DesignStandard.BS5400 and self.fcu_mpa is None:
            raise ValueError(
                "BS 5400 design requires explicit fcu_mpa; no Eurocode cylinder-to-cube "
                "conversion is performed automatically."
            )


class SurfacingLayer(BaseModel):
    name: str
    thickness_m: PositiveFloat
    density_kn_m3: PositiveFloat
    y_start_m: float
    y_end_m: float
    x_start_m: float = 0.0
    x_end_m: float | None = None
    stage: PermanentActionStage = PermanentActionStage.SUPERIMPOSED

    @model_validator(mode="after")
    def validate_layer(self) -> SurfacingLayer:
        if not self.name.strip():
            raise ValueError("Surfacing-layer name cannot be empty.")
        if self.y_end_m <= self.y_start_m:
            raise ValueError("Surfacing-layer transverse bounds must define positive width.")
        if self.x_start_m < 0.0:
            raise ValueError("Surfacing-layer longitudinal start cannot be negative.")
        if self.x_end_m is not None and self.x_end_m <= self.x_start_m:
            raise ValueError("Surfacing-layer longitudinal bounds must define positive length.")
        return self

    @property
    def pressure_kn_m2(self) -> float:
        return float(self.thickness_m * self.density_kn_m3)


class PermanentLineAction(BaseModel):
    name: str
    magnitude_kn_m: PositiveFloat
    y_m: float
    x_start_m: float = 0.0
    x_end_m: float | None = None
    stage: PermanentActionStage = PermanentActionStage.SUPERIMPOSED

    @model_validator(mode="after")
    def validate_action(self) -> PermanentLineAction:
        if not self.name.strip():
            raise ValueError("Permanent line-action name cannot be empty.")
        if self.x_start_m < 0.0:
            raise ValueError("Permanent line-action longitudinal start cannot be negative.")
        if self.x_end_m is not None and self.x_end_m <= self.x_start_m:
            raise ValueError("Permanent line-action bounds must define positive length.")
        return self


class PermanentActionModel(BaseModel):
    surfacing_layers: list[SurfacingLayer] = Field(default_factory=list)
    line_actions: list[PermanentLineAction] = Field(default_factory=list)


class BarLayer(BaseModel):
    count: PositiveInt
    diameter_mm: PositiveFloat

    @property
    def area_mm2(self) -> float:
        return float(self.count) * pi * float(self.diameter_mm) ** 2 / 4.0


class LongitudinalReinforcement(BaseModel):
    layers: list[BarLayer] = Field(min_length=1)

    @property
    def total_area_mm2(self) -> float:
        return sum(layer.area_mm2 for layer in self.layers)


class SingleSpanBridgeGeometry(BaseModel):
    span_m: PositiveFloat
    physical_girder_length_m: PositiveFloat | None = None
    deck_width_m: PositiveFloat
    carriageway_width_m: PositiveFloat
    carriageway_offset_m: float = 0.0
    girder_count: PositiveInt
    girder_spacing_m: PositiveFloat
    girder_profile: GirderProfile
    deck: DeckConstruction = Field(default_factory=DeckConstruction)

    @model_validator(mode="after")
    def validate_geometry(self) -> SingleSpanBridgeGeometry:
        if self.girder_count < 2:
            raise ValueError("At least two longitudinal girders are required.")
        if self.carriageway_width_m > self.deck_width_m:
            raise ValueError("Carriageway width cannot exceed deck width.")
        half_deck = float(self.deck_width_m) / 2.0
        left = float(self.carriageway_offset_m) - float(self.carriageway_width_m) / 2.0
        right = float(self.carriageway_offset_m) + float(self.carriageway_width_m) / 2.0
        if left < -half_deck - 1.0e-9 or right > half_deck + 1.0e-9:
            raise ValueError("Carriageway lies outside the physical deck.")
        if self.edge_overhang_m < -1.0e-9:
            raise ValueError(
                "Girder count and spacing place exterior girder lines outside the deck."
            )
        return self

    @property
    def girder_line_width_m(self) -> float:
        return (int(self.girder_count) - 1) * float(self.girder_spacing_m)

    @property
    def edge_overhang_m(self) -> float:
        return (float(self.deck_width_m) - self.girder_line_width_m) / 2.0

    @property
    def total_structural_depth_m(self) -> float:
        return float(self.girder_profile.total_depth_m) + self.deck.physical_depth_m


class BridgeProject(BaseModel):
    name: str
    geometry: SingleSpanBridgeGeometry
    materials: MaterialProperties
    permanent_actions: PermanentActionModel = Field(default_factory=PermanentActionModel)
    provided_longitudinal_reinforcement: LongitudinalReinforcement | None = None

    @model_validator(mode="after")
    def validate_project(self) -> BridgeProject:
        if not self.name.strip():
            raise ValueError("Project name cannot be empty.")
        half_width = float(self.geometry.deck_width_m) / 2.0
        span = float(self.geometry.span_m)
        for layer in self.permanent_actions.surfacing_layers:
            if layer.y_start_m < -half_width or layer.y_end_m > half_width:
                raise ValueError("Surfacing layer lies outside the physical deck width.")
            if layer.x_start_m >= span or (
                layer.x_end_m is not None and layer.x_end_m > span
            ):
                raise ValueError("Surfacing layer lies outside the span.")
        for action in self.permanent_actions.line_actions:
            if action.y_m < -half_width or action.y_m > half_width:
                raise ValueError("Permanent line action lies outside the physical deck width.")
            if action.x_start_m >= span or (
                action.x_end_m is not None and action.x_end_m > span
            ):
                raise ValueError("Permanent line action lies outside the span.")
        return self
