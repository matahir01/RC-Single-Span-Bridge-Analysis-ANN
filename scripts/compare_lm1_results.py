"""Compare old/new LM1 results from the same solver platform and input."""

import argparse
import json
from math import isclose
from pathlib import Path


def compare(old: object, new: object, path: str = "") -> None:
    if isinstance(old, dict):
        assert isinstance(new, dict) and old.keys() == new.keys(), path
        for key, value in old.items():
            if key != "elapsed_s":
                compare(value, new[key], f"{path}.{key}")
    elif isinstance(old, list):
        assert isinstance(new, list) and len(old) == len(new), path
        for index, (left, right) in enumerate(zip(old, new, strict=True)):
            compare(left, right, f"{path}[{index}]")
    elif isinstance(old, float):
        assert isinstance(new, int | float) and isclose(
            old, new, rel_tol=1e-9, abs_tol=1e-7,
        ), f"{path}: {old} != {new}"
    else:
        assert old == new, f"{path}: {old!r} != {new!r}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("--exact", action="store_true",
                        help="Require identical JSON fields except elapsed time.")
    args = parser.parse_args()
    old, new = (json.loads(path.read_text(encoding="utf-8"))
                for path in (args.old, args.new))
    if args.exact:
        assert {key: value for key, value in old.items() if key != "elapsed_s"} == {
            key: value for key, value in new.items() if key != "elapsed_s"
        }, "The LM1 outputs differ."
    else:
        compare(old, new)
    scope = "cases, IDs, loads and combinations"
    if "design" in old:
        scope += " and design"
    print(f"LM1 governing {scope} match; {old['elapsed_s'] / new['elapsed_s']:.2f}x faster")


if __name__ == "__main__":
    main()
