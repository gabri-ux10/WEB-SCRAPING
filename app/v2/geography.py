from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

REFERENCE = Path(__file__).resolve().parents[2] / "data/reference/un_m49_countries.csv"


@lru_cache(maxsize=1)
def _country_index(path: str = str(REFERENCE)) -> dict[str, dict]:
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return {row["iso_alpha2"].upper(): row for row in csv.DictReader(stream)}


def m49_region_for_country(country_code: str, *, path: Path = REFERENCE) -> str:
    if len(country_code or "") != 2:
        raise ValueError("A two-letter ISO 3166-1 alpha-2 country code is required")
    try:
        return _country_index(str(path))[country_code.upper()]["region_code"]
    except FileNotFoundError as exc:
        raise RuntimeError("The verified UN M49 country reference has not been generated") from exc
    except KeyError as exc:
        raise ValueError(f"No UN M49 mapping is loaded for ISO country code {country_code!r}") from exc
