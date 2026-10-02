"""Require identical BS traffic cases, stations and combinations on one runner."""

import argparse
import gzip
import json
from pathlib import Path


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
    assert old == new, "BS 5400 traffic envelopes, cases or combinations changed."
    print(f"BS traffic outputs identical; {old_time:.2f} s -> {new_time:.2f} s "
          f"({old_time / new_time:.2f}x).")


if __name__ == "__main__":
    main()
