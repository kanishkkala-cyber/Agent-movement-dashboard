"""Run before deploy: python scripts/preflight_deploy.py"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    errors: list[str] = []
    required_dirs = ["Data-day-wise", "Site Locations"]
    required_files = ["app.py", "requirements.txt", "runtime.txt"]
    site_files = ["MFC Yards.xlsx", "Service centres.xlsx", "Turno Stores.xlsx"]

    for f in required_files:
        if not (ROOT / f).is_file():
            errors.append(f"Missing file: {f}")

    for d in required_dirs:
        p = ROOT / d
        if not p.is_dir():
            errors.append(f"Missing folder: {d}/")
            continue
        if d == "Data-day-wise":
            xlsx = list(p.glob("*.xlsx"))
            if not xlsx:
                errors.append("Data-day-wise/ has no .xlsx files")
            else:
                print(f"OK  Data-day-wise: {len(xlsx)} Excel file(s)")
        if d == "Site Locations":
            for sf in site_files:
                if not (p / sf).is_file():
                    errors.append(f"Missing Site Locations/{sf}")

    try:
        import streamlit  # noqa: F401
        import pandas  # noqa: F401
        import folium  # noqa: F401

        print("OK  Python dependencies importable")
    except ImportError as e:
        errors.append(f"Import error: {e}")

    if errors:
        print("PREFLIGHT FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("PREFLIGHT PASSED — ready for Streamlit Cloud deploy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
