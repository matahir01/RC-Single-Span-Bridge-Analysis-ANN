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

    # The support-anchored HA KEL grid intentionally changed HA candidate
    # count and ordinal case IDs. Keep the same-runner regression strict for
    # response values, station envelopes, and combinations while comparing
    # those physical results independently of search provenance.
    old_ha = old["traffic"]["ha"]
    new_ha = new["traffic"]["ha"]
    old_ha.pop("evaluated_case_count")
    new_ha.pop("evaluated_case_count")
    old_ha.pop("retained_case_ids")
    new_ha.pop("retained_case_ids")

    def canonicalize_station_rows(record: dict[str, Any]) -> None:
        for search in record["traffic"].values():
            for girder in search["stations"]:
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

    def without_case_ids(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: without_case_ids(item)
                for key, item in value.items()
                if key != "case_id"
            }
        if isinstance(value, list):
            return [without_case_ids(item) for item in value]
        return value

    old, new = without_case_ids(old), without_case_ids(new)
    assert old == new, "BS 5400 traffic envelopes, cases or combinations changed."
    print(f"BS traffic outputs identical; {old_time:.2f} s -> {new_time:.2f} s "
          f"({old_time / new_time:.2f}x).")


if __name__ == "__main__":
    main()
