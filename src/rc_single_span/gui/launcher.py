from __future__ import annotations


def main() -> int:
    try:
        from rc_single_span.gui.app import main as gui_main
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("PySide6"):
            raise SystemExit(
                'PySide6 is required for the desktop GUI. Install with: pip install -e ".[gui]"'
            ) from exc
        raise
    return gui_main()


if __name__ == "__main__":
    raise SystemExit(main())
