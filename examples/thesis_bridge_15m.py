from reference_bridge_15m import reference_bridge_15m

from rc_single_span.core.models import MaterialProperties


def thesis_bridge_15m():
    """15 m research bridge aligned with the thesis material/design basis.

    Geometry is intentionally identical to the externally verified 15 m reference
    bridge: seven 400 x 950 mm precast girders at 1.70 m centres, 11.0 m deck and
    75 + 175 mm deck build-up. The research profile replaces the old verification-
    benchmark C25/30 / Grade-410 material assumptions with the thesis C35/45 and
    B500 basis.

    The surfacing, barrier and service actions inherited from ``reference_bridge_15m``
    remain explicitly labelled benchmark assumptions in that source file. They are
    not represented as surveyed/as-built project data.
    """

    bridge = reference_bridge_15m()
    materials = MaterialProperties(
        fck_mpa=35.0,
        fcu_mpa=45.0,
        fyk_mpa=500.0,
        concrete_density_kn_m3=25.0,
        elastic_modulus_mpa=34000.0,
    )
    return bridge.model_copy(
        update={
            "name": "15 m C35/45 B500 thesis research bridge",
            "materials": materials,
        }
    )


if __name__ == "__main__":
    bridge = thesis_bridge_15m()
    print(bridge.model_dump_json(indent=2))
