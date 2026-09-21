from __future__ import annotations

import argparse
import os
from pathlib import Path

from reference_bridge_15m import reference_bridge_15m

from rc_single_span.verification.export_bundle import (
    write_construction_verification_bundle,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export Stage-8 construction/permanent-action STAAD verification "
            "packages for the 15 m reference bridge."
        )
    )
    parser.add_argument(
        "--elastic-modulus-mpa",
        type=float,
        required=True,
        help="Explicit concrete elastic modulus used for the verification run.",
    )
    parser.add_argument(
        "--elastic-modulus-basis",
        required=True,
        help=(
            "Traceable basis for the supplied modulus, e.g. project test data "
            "or a named code-derived Ecm basis."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="stage8_staad_bundle",
        help="Directory where the verification package tree will be written.",
    )
    parser.add_argument(
        "--repository-sha",
        default=os.getenv("GITHUB_SHA", ""),
        help="Optional repository commit SHA recorded in the bundle index.",
    )
    parser.add_argument(
        "--longitudinal-divisions",
        type=int,
        default=8,
        help="Supplemental verification beam divisions; exact load/response stations are added too.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.elastic_modulus_mpa <= 0.0:
        raise SystemExit("--elastic-modulus-mpa must be positive.")

    bridge = reference_bridge_15m()
    materials = bridge.materials.model_copy(
        update={"elastic_modulus_mpa": args.elastic_modulus_mpa}
    )
    bridge = bridge.model_copy(update={"materials": materials})

    result = write_construction_verification_bundle(
        bridge,
        Path(args.output_dir),
        elastic_modulus_basis=args.elastic_modulus_basis,
        repository_sha=args.repository_sha or None,
        longitudinal_divisions=args.longitudinal_divisions,
    )
    print(f"Wrote {len(result.written_files)} files to {result.output_directory}")
    print(f"Bundle index: {result.index_path}")
    print(
        "Internal construction cross-check: "
        + ("PASS" if result.suite.passes_internal_crosscheck else "FAIL")
    )
    print("External STAAD verification: PENDING")


if __name__ == "__main__":
    main()
