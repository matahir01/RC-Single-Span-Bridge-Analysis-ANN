from rc_single_span.core.models import (
    BridgeProject,
    DeckConstruction,
    IGirderProfile,
    MaterialProperties,
    PermanentActionModel,
    PermanentLineAction,
    SingleSpanBridgeGeometry,
    SurfacingLayer,
)


def reference_bridge_20m_i() -> BridgeProject:
    """Independent 20 m haunched-I benchmark with explicit nominal actions.

    This case is a verification benchmark, not a hard-coded reinforcement target.
    It exists beside the 15 m rectangular research bridge so future engine
    changes must work for both the research geometry and a field-style I-girder.
    """

    return BridgeProject(
        name="20 m single-span haunched RC I-girder benchmark",
        geometry=SingleSpanBridgeGeometry(
            span_m=20.0,
            physical_girder_length_m=20.0,
            deck_width_m=11.0,
            carriageway_width_m=7.0,
            girder_count=7,
            girder_spacing_m=1.70,
            girder_profile=IGirderProfile(
                top_flange_width_m=0.40,
                top_flange_thickness_m=0.15,
                top_haunch_depth_m=0.15,
                web_width_m=0.25,
                web_depth_m=0.50,
                bottom_haunch_depth_m=0.20,
                bottom_flange_width_m=0.40,
                bottom_flange_thickness_m=0.20,
            ),
            deck=DeckConstruction(
                precast_false_slab_depth_m=0.075,
                in_situ_slab_depth_m=0.175,
                false_slab_composite_participation=False,
                in_situ_slab_composite_participation=True,
            ),
        ),
        materials=MaterialProperties(
            fck_mpa=35.0,
            fcu_mpa=45.0,
            fyk_mpa=500.0,
            concrete_density_kn_m3=25.0,
            elastic_modulus_mpa=34000.0,
        ),
        permanent_actions=PermanentActionModel(
            surfacing_layers=[
                SurfacingLayer(
                    name="80 mm carriageway surfacing (benchmark assumption)",
                    thickness_m=0.080,
                    density_kn_m3=23.0,
                    y_start_m=-3.5,
                    y_end_m=3.5,
                    x_end_m=20.0,
                ),
                SurfacingLayer(
                    name="left 100 mm footway topping (benchmark assumption)",
                    thickness_m=0.100,
                    density_kn_m3=25.0,
                    y_start_m=-5.5,
                    y_end_m=-3.5,
                    x_end_m=20.0,
                ),
                SurfacingLayer(
                    name="right 100 mm footway topping (benchmark assumption)",
                    thickness_m=0.100,
                    density_kn_m3=25.0,
                    y_start_m=3.5,
                    y_end_m=5.5,
                    x_end_m=20.0,
                ),
            ],
            line_actions=[
                PermanentLineAction(
                    name="left 300x300 kerb (benchmark assumption)",
                    magnitude_kn_m=2.25,
                    y_m=-3.65,
                    x_end_m=20.0,
                ),
                PermanentLineAction(
                    name="right 300x300 kerb (benchmark assumption)",
                    magnitude_kn_m=2.25,
                    y_m=3.65,
                    x_end_m=20.0,
                ),
                PermanentLineAction(
                    name="left barrier (benchmark assumption)",
                    magnitude_kn_m=10.0,
                    y_m=-5.25,
                    x_end_m=20.0,
                ),
                PermanentLineAction(
                    name="right barrier (benchmark assumption)",
                    magnitude_kn_m=10.0,
                    y_m=5.25,
                    x_end_m=20.0,
                ),
                PermanentLineAction(
                    name="left services (benchmark assumption)",
                    magnitude_kn_m=1.0,
                    y_m=-4.8,
                    x_end_m=20.0,
                ),
                PermanentLineAction(
                    name="right services (benchmark assumption)",
                    magnitude_kn_m=1.0,
                    y_m=4.8,
                    x_end_m=20.0,
                ),
            ],
        ),
    )


if __name__ == "__main__":
    bridge = reference_bridge_20m_i()
    profile = bridge.geometry.girder_profile
    print(bridge.model_dump_json(indent=2))
    print(f"Precast girder area = {profile.area_m2:.6f} m2")
