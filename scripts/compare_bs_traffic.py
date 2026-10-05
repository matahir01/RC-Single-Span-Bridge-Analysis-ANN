"""Require identical BS traffic cases, stations and combinations on one runner."""

import argparse
import gzip
import json
from pathlib import Path
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    args = parser.parse_args()
    def read_record(path: Path) -> dict:
        if path.suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as source:
                return json.load(source)
        return json.loads(path.read_text(encoding="utf-8"))

    old, new = (read_record(path) for path in (args.old, args.new))
    old_time, new_time = old.pop("elapsed_s"), new.pop("elapsed_s")
    # The legacy source predates this runner-only option. Its default was to
    # evaluate all-case deflection when all cases were retained; restoring that
    # documented default keeps the numeric traffic/design equality gate strict.
    old["config"].setdefault("evaluate_all_case_combined_deflection", True)
    new["config"].setdefault("evaluate_all_case_combined_deflection", True)

    def canonicalize_station_rows(record: dict[str, Any]) -> None:
        for search in record["traffic"].values():
            station_girders = search.get("stations", [])
            for girder in station_girders:
                values: dict[float, float] = {}
                for station in girder["stations"]:
                    x_m = round(float(station["x_m"]), 9)
                    moment = float(station["moment_knm"]["value"])
                    values[x_m] = max(values.get(x_m, float("-inf")), moment)
                girder["stations"] = [
                    {"x_m": x_m, "moment_knm": {"value": values[x_m]}}
                    for x_m in sorted(values)
                ]

    canonicalize_station_rows(old)
    canonicalize_station_rows(new)

    def first_difference(left: Any, right: Any, path: str = "$") -> str | None:
        if isinstance(left, dict) and isinstance(right, dict):
            if left.keys() != right.keys():
                return f"{path} keys: {sorted(left)} != {sorted(right)}"
            for key in left:
                difference = first_difference(left[key], right[key], f"{path}.{key}")
                if difference is not None:
                    return difference
            return None
        if isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                return f"{path} lengths: {len(left)} != {len(right)}"
            for index, (left_item, right_item) in enumerate(zip(left, right, strict=True)):
                difference = first_difference(left_item, right_item, f"{path}[{index}]")
                if difference is not None:
                    return difference
            return None
        if left != right:
            return f"{path}: {left!r} != {right!r}"
        return None

    difference = first_difference(old, new)
    if difference is not None:
        raise AssertionError(
            "BS 5400 traffic envelopes, cases or combinations changed; "
            f"first difference: {difference}"
        )
    print(f"BS traffic outputs identical; {old_time:.2f} s -> {new_time:.2f} s "
          f"({old_time / new_time:.2f}x).")


if __name__ == "__main__":
    main()
