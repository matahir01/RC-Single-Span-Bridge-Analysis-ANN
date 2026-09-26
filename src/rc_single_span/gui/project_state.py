from __future__ import annotations

from dataclasses import asdict, dataclass

from rc_single_span.core.models import (
    BarLayer,
    BridgeProject,
    DeckConstruction,
    IGirderProfile,
    LongitudinalReinforcement,
    MaterialProperties,
    PermanentActionModel,
    PermanentLineAction,
    RectangularGirderProfile,
    SectionType,
    SingleSpanBridgeGeometry,
    SurfacingLayer,
    TGirderProfile,
)


@dataclass(frozen=True)
class GuiProjectState:
    """Editable bridge inputs used by the desktop GUI.

    The defaults reproduce the current 15 m C35/45 B500 thesis bridge geometry.
    Permanent actions are retained as explicit benchmark assumptions until the
    project-specific values are supplied by the user.
    """

    name: str = "15 m C35/45 B500 thesis bridge"
    span_m: float = 15.0
    physical_girder_length_m: float = 14.95
    deck_width_m: float = 11.0
    carriageway_width_m: float = 7.0
    carriageway_offset_m: float = 0.0
    girder_count: int = 7
    girder_spacing_m: float = 1.70
    section_type: str = SectionType.RECTANGULAR.value

    rectangular_width_m: float = 0.40
    rectangular_depth_m: float = 0.95

    t_flange_width_m: float = 1.70
    t_flange_thickness_m: float = 0.175
    t_web_width_m: float = 0.40
    t_total_depth_m: float = 1.125

    i_top_flange_width_m: float = 0.40
    i_top_flange_thickness_m: float = 0.15
    i_top_haunch_depth_m: float = 0.0
    i_web_width_m: float = 0.20
    i_web_depth_m: float = 0.65
    i_bottom_haunch_depth_m: float = 0.0
    i_bottom_flange_width_m: float = 0.40
    i_bottom_flange_thickness_m: float = 0.15

    false_slab_depth_m: float = 0.075
    in_situ_slab_depth_m: float = 0.175
    false_slab_composite: bool = False
    in_situ_slab_composite: bool = True

    fck_mpa: float = 35.0
    fcu_mpa: float = 45.0
    fyk_mpa: float = 500.0
    concrete_density_kn_m3: float = 25.0
    elastic_modulus_mpa: float = 34000.0

    reinforcement_layers: int = 4
    bars_per_layer: int = 4
    bar_diameter_mm: float = 32.0

    surfacing_thickness_m: float = 0.080
    surfacing_density_kn_m3: float = 22.0
    barrier_kn_m: float = 10.0
    services_kn_m: float = 2.0

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, values: dict[str, object]) -> GuiProjectState:
        known = {field for field in cls.__dataclass_fields__}
        unexpected = set(values) - known
        if unexpected:
            raise ValueError(f"Unknown GUI project fields: {sorted(unexpected)}")
        return cls(**values)

    def _profile(self):
        section = SectionType(self.section_type)
        if section is SectionType.RECTANGULAR:
            return RectangularGirderProfile(
                width_m=self.rectangular_width_m,
                depth_m=self.rectangular_depth_m,
            )
        if section is SectionType.T:
            return TGirderProfile(
                flange_width_m=self.t_flange_width_m,
                flange_thickness_m=self.t_flange_thickness_m,
                web_width_m=self.t_web_width_m,
                total_depth_m=self.t_total_depth_m,
            )
        return IGirderProfile(
            top_flange_width_m=self.i_top_flange_width_m,
            top_flange_thickness_m=self.i_top_flange_thickness_m,
            top_haunch_depth_m=self.i_top_haunch_depth_m,
            web_width_m=self.i_web_width_m,
            web_depth_m=self.i_web_depth_m,
            bottom_haunch_depth_m=self.i_bottom_haunch_depth_m,
            bottom_flange_width_m=self.i_bottom_flange_width_m,
            bottom_flange_thickness_m=self.i_bottom_flange_thickness_m,
        )

    def build_project(self) -> BridgeProject:
        half_deck = 0.5 * self.deck_width_m
        half_carriageway = 0.5 * self.carriageway_width_m
        reinforcement = LongitudinalReinforcement(
            layers=[
                BarLayer(count=self.bars_per_layer, diameter_mm=self.bar_diameter_mm)
                for _ in range(self.reinforcement_layers)
            ]
        )
        permanent_actions = PermanentActionModel(
            surfacing_layers=[
                SurfacingLayer(
                    name="carriageway surfacing (GUI input)",
                    thickness_m=self.surfacing_thickness_m,
                    density_kn_m3=self.surfacing_density_kn_m3,
                    y_start_m=self.carriageway_offset_m - half_carriageway,
                    y_end_m=self.carriageway_offset_m + half_carriageway,
                    x_end_m=self.span_m,
                )
            ],
            line_actions=[
                PermanentLineAction(
                    name="left safety barrier (GUI input)",
                    magnitude_kn_m=self.barrier_kn_m,
                    y_m=-half_deck,
                    x_end_m=self.span_m,
                ),
                PermanentLineAction(
                    name="right safety barrier (GUI input)",
                    magnitude_kn_m=self.barrier_kn_m,
                    y_m=half_deck,
                    x_end_m=self.span_m,
                ),
                PermanentLineAction(
                    name="left services (GUI input)",
                    magnitude_kn_m=self.services_kn_m,
                    y_m=-max(half_deck - 0.7, 0.0),
                    x_end_m=self.span_m,
                ),
                PermanentLineAction(
                    name="right services (GUI input)",
                    magnitude_kn_m=self.services_kn_m,
                    y_m=max(half_deck - 0.7, 0.0),
                    x_end_m=self.span_m,
                ),
            ],
        )
        return BridgeProject(
            name=self.name,
            geometry=SingleSpanBridgeGeometry(
                span_m=self.span_m,
                physical_girder_length_m=self.physical_girder_length_m,
                deck_width_m=self.deck_width_m,
                carriageway_width_m=self.carriageway_width_m,
                carriageway_offset_m=self.carriageway_offset_m,
                girder_count=self.girder_count,
                girder_spacing_m=self.girder_spacing_m,
                girder_profile=self._profile(),
                deck=DeckConstruction(
                    precast_false_slab_depth_m=self.false_slab_depth_m,
                    in_situ_slab_depth_m=self.in_situ_slab_depth_m,
                    false_slab_composite_participation=self.false_slab_composite,
                    in_situ_slab_composite_participation=self.in_situ_slab_composite,
                ),
            ),
            materials=MaterialProperties(
                fck_mpa=self.fck_mpa,
                fcu_mpa=self.fcu_mpa,
                fyk_mpa=self.fyk_mpa,
                concrete_density_kn_m3=self.concrete_density_kn_m3,
                elastic_modulus_mpa=self.elastic_modulus_mpa,
            ),
            permanent_actions=permanent_actions,
            provided_longitudinal_reinforcement=reinforcement,
        )
