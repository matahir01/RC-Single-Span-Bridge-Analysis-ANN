from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO

StaadResultKey = tuple[str, int, str, str]


@dataclass(frozen=True)
class StaadAnlDifference:
    key: StaadResultKey
    expected: float
    actual: float
    absolute_difference: float
    allowed_difference: float

    @property
    def passes(self) -> bool:
        return self.absolute_difference <= self.allowed_difference


@dataclass(frozen=True)
class StaadAnlComparisonReport:
    comparisons: tuple[StaadAnlDifference, ...]
    missing_keys: tuple[StaadResultKey, ...]
    unexpected_keys: tuple[StaadResultKey, ...]

    @property
    def passes(self) -> bool:
        return (
            bool(self.comparisons)
            and not self.missing_keys
            and not self.unexpected_keys
            and all(item.passes for item in self.comparisons)
        )

    @property
    def failure_count(self) -> int:
        return sum(not item.passes for item in self.comparisons)


def _clean_control_text(text: str) -> str:
    return "".join(
        character
        if character in "\n\r\t" or ord(character) >= 32
        else " "
        for character in text
    )


def _integer(token: str) -> int | None:
    try:
        return int(token)
    except ValueError:
        return None


def _floats(tokens: list[str]) -> tuple[float, ...] | None:
    try:
        return tuple(float(token) for token in tokens)
    except ValueError:
        return None


def parse_staad_anl(text: str) -> dict[StaadResultKey, float]:
    """Parse the direct global result fields exported for verification.

    STAAD reports joint translations in centimetres for the kN-m models, so DZ
    is converted to metres. Support FZ and global member-end FZ/MX/MY are
    already reported in kN and kNm.
    """

    results: dict[StaadResultKey, float] = {}
    state: str | None = None
    current_member: int | None = None

    for raw_line in _clean_control_text(text).splitlines():
        line = raw_line.strip()
        upper = line.upper()

        if "SUPPORT REACTIONS -UNIT" in upper:
            state = "reaction"
            current_member = None
            continue
        if "MEMBER END FORCES" in upper:
            state = "member"
            current_member = None
            continue
        if "JOINT DISPLACEMENT (CM" in upper:
            state = "displacement"
            current_member = None
            continue
        if "END OF LATEST ANALYSIS RESULT" in upper:
            state = None
            current_member = None
            continue

        tokens = line.split()
        if state in {"reaction", "displacement"} and len(tokens) == 8:
            node_id = _integer(tokens[0])
            load_id = _integer(tokens[1])
            values = _floats(tokens[2:])
            if node_id is None or load_id is None or values is None:
                continue
            if state == "reaction":
                results[("support_reaction", node_id, "", "FZ")] = values[2]
            else:
                results[("node_displacement", node_id, "", "DZ")] = values[2] / 100.0
            continue

        if state != "member":
            continue

        if len(tokens) == 9:
            member_id = _integer(tokens[0])
            load_id = _integer(tokens[1])
            joint_id = _integer(tokens[2])
            values = _floats(tokens[3:])
            if (
                member_id is None
                or load_id is None
                or joint_id is None
                or values is None
            ):
                current_member = None
                continue
            current_member = member_id
            end = "i"
        elif len(tokens) == 7 and current_member is not None:
            joint_id = _integer(tokens[0])
            values = _floats(tokens[1:])
            if joint_id is None or values is None:
                continue
            member_id = current_member
            end = "j"
        else:
            continue

        results[("member_end_force", member_id, end, "FZ")] = values[2]
        results[("member_end_force", member_id, end, "MX")] = values[3]
        results[("member_end_force", member_id, end, "MY")] = values[4]

    return results


def parse_expected_results_csv(
    text: str,
) -> dict[StaadResultKey, tuple[float, str]]:
    reader = csv.DictReader(StringIO(text))
    required = {
        "result_type",
        "object_id",
        "end",
        "component",
        "value",
        "unit",
    }
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise ValueError("Expected-results CSV is missing required columns.")

    expected: dict[StaadResultKey, tuple[float, str]] = {}
    for row in reader:
        key = (
            (row.get("result_type") or "").strip(),
            int((row.get("object_id") or "").strip()),
            (row.get("end") or "").strip(),
            (row.get("component") or "").strip().upper(),
        )
        if key in expected:
            raise ValueError(f"Duplicate expected STAAD result key: {key}.")
        expected[key] = (
            float((row.get("value") or "").strip()),
            (row.get("unit") or "").strip(),
        )
    return expected


def _allowed_difference(
    key: StaadResultKey,
    expected_value: float,
) -> float:
    result_type, _, _, _ = key
    if result_type == "node_displacement":
        return 3.0e-6 + 1.0e-4 * abs(expected_value)
    if result_type in {"support_reaction", "member_end_force"}:
        return 0.02 + 1.0e-4 * abs(expected_value)
    raise ValueError(f"Unsupported STAAD result type: {result_type}.")


def compare_staad_anl_to_expected_csv(
    anl_text: str,
    expected_csv: str,
) -> StaadAnlComparisonReport:
    """Compare a genuine STAAD .ANL return against its expected-results CSV."""

    actual = parse_staad_anl(anl_text)
    expected = parse_expected_results_csv(expected_csv)
    expected_keys = set(expected)
    actual_keys = set(actual)

    comparisons = tuple(
        StaadAnlDifference(
            key=key,
            expected=expected[key][0],
            actual=actual[key],
            absolute_difference=abs(actual[key] - expected[key][0]),
            allowed_difference=_allowed_difference(key, expected[key][0]),
        )
        for key in sorted(expected_keys & actual_keys)
    )

    return StaadAnlComparisonReport(
        comparisons=comparisons,
        missing_keys=tuple(sorted(expected_keys - actual_keys)),
        unexpected_keys=tuple(sorted(actual_keys - expected_keys)),
    )
