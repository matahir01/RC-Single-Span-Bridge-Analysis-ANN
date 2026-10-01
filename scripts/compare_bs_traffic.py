"""Require identical BS traffic cases, stations and combinations on one runner."""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    args = parser.parse_args()
    old, new = (json.loads(path.read_text(encoding="utf-8"))
                for path in (args.old, args.new))
    old_time, new_time = old.pop("elapsed_s"), new.pop("elapsed_s")
    assert old == new, "BS 5400 traffic envelopes, cases or combinations changed."
    print(f"BS traffic outputs identical; {old_time:.2f} s -> {new_time:.2f} s "
          f"({old_time / new_time:.2f}x).")


if __name__ == "__main__":
    main()
