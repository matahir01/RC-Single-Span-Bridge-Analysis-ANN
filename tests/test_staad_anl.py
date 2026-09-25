from rc_single_span.verification.staad_anl import (
    compare_staad_anl_to_expected_csv,
    parse_staad_anl,
)


def _anl() -> str:
    return """
SUPPORT REACTIONS -UNIT KNS  METE    STRUCTURE TYPE = SPACE
 JOINT  LOAD   FORCE-X   FORCE-Y   FORCE-Z     MOM-X     MOM-Y     MOM Z
 1 7 0.00 0.00 10.00 0.00 0.00 0.00
 ************** END OF LATEST ANALYSIS RESULT **************

MEMBER END FORCES    STRUCTURE TYPE = SPACE
 ALL UNITS ARE -- KNS  METE     (GLOBAL)
 MEMBER  LOAD  JT      FX        FY       FZ        MX        MY         MZ
 1 7 1 0.00 0.00 10.00 1.00 2.00 0.00
     2 0.00 0.00 -10.00 -1.00 -2.00 0.00
 ************** END OF LATEST ANALYSIS RESULT **************

JOINT DISPLACEMENT (CM   RADIANS)    STRUCTURE TYPE = SPACE
 JOINT  LOAD   X-TRANS   Y-TRANS   Z-TRANS   X-ROTAN   Y-ROTAN   Z-ROTAN
 1 7 0.0000 0.0000 -0.1000 0.0000 0.0000 0.0000
 2 7 0.0000 0.0000 -0.2000 0.0000 0.0000 0.0000
 ************** END OF LATEST ANALYSIS RESULT **************
"""


def _expected() -> str:
    return """result_type,object_id,end,component,value,unit,comparison_status
node_displacement,1,,DZ,-0.001,m,direct_global
node_displacement,2,,DZ,-0.002,m,direct_global
support_reaction,1,,FZ,10.0,kN,direct_global
member_end_force,1,i,FZ,10.0,kN,direct_global_mapping
member_end_force,1,i,MX,1.0,kNm,direct_global_mapping
member_end_force,1,i,MY,2.0,kNm,direct_global_mapping
member_end_force,1,j,FZ,-10.0,kN,direct_global_mapping
member_end_force,1,j,MX,-1.0,kNm,direct_global_mapping
member_end_force,1,j,MY,-2.0,kNm,direct_global_mapping
"""


def test_parse_staad_anl_maps_direct_global_components_and_units() -> None:
    parsed = parse_staad_anl(_anl())

    assert parsed[("node_displacement", 1, "", "DZ")] == -0.001
    assert parsed[("support_reaction", 1, "", "FZ")] == 10.0
    assert parsed[("member_end_force", 1, "i", "FZ")] == 10.0
    assert parsed[("member_end_force", 1, "j", "MY")] == -2.0


def test_anl_comparison_requires_every_expected_field() -> None:
    report = compare_staad_anl_to_expected_csv(_anl(), _expected())
    assert report.passes
    assert len(report.comparisons) == 9
    assert report.failure_count == 0

    missing_j_end = _anl().replace(
        "     2 0.00 0.00 -10.00 -1.00 -2.00 0.00\n",
        "",
    )
    incomplete = compare_staad_anl_to_expected_csv(missing_j_end, _expected())
    assert not incomplete.passes
    assert len(incomplete.missing_keys) == 3
    assert (
        "member_end_force",
        1,
        "j",
        "FZ",
    ) in incomplete.missing_keys


def test_anl_comparison_enforces_engineering_tolerance() -> None:
    changed = _anl().replace(
        " 1 7 0.00 0.00 10.00 0.00 0.00 0.00",
        " 1 7 0.00 0.00 10.50 0.00 0.00 0.00",
    )
    report = compare_staad_anl_to_expected_csv(changed, _expected())
    assert not report.passes
    assert report.failure_count == 1
