from rc_single_span.core.models import (
    BarLayer,
    BridgeProject,
    DeckConstruction,
    LongitudinalReinforcement,
    MaterialProperties,
    RectangularGirderProfile,
    SingleSpanBridgeGeometry,
)


def reference_bridge_15m() -> BridgeProject:
    """Traceable 15 m reference bridge for regression and verification."""

    return BridgeProject(
        name="15 m single-span RC girder reference",
        geometry=SingleSpanBridgeGeometry(
            span_m=15.0,
            physical_girder_length_m=14.95,
            deck_width_m=11.0,
            carriageway_width_m=7.0,
            girder_count=7,
            girder_spacing_m=1.70,
            girder_profile=RectangularGirderProfile(width_m=0.40, depth_m=0.95),
            deck=DeckConstruction(
                precast_false_slab_depth_m=0.075,
                in_situ_slab_depth_m=0.175,
                false_slab_composite_participation=False,
                in_situ_slab_composite_participation=True,
            ),
        ),
        materials=MaterialProperties(
            fck_mpa=25.0,
            fcu_mpa=30.0,
            fyk_mpa=410.0,
            concrete_density_kn_m3=24.0,
        ),
        provided_longitudinal_reinforcement=LongitudinalReinforcement(
            layers=[BarLayer(count=4, diameter_mm=32.0) for _ in range(4)]
        ),
    )


if __name__ == "__main__":
    bridge = reference_bridge_15m()
    print(bridge.model_dump_json(indent=2))
    print(
        "Provided longitudinal steel area = "
        f"{bridge.provided_longitudinal_reinforcement.total_area_mm2:.1f} mm2"
    )
