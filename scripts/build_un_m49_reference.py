"""Fetch the official UN M49 table and save ISO-2 country/area mappings."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

URL = "https://unstats.un.org/unsd/methodology/m49/overview"
OUTPUT = Path(__file__).resolve().parents[1] / "data" / "reference" / "un_m49_countries.csv"
FIELDS = [
    "country_or_area", "m49_code", "iso_alpha2", "iso_alpha3",
    "region_code", "region_name", "subregion_code", "subregion_name",
    "intermediate_region_code", "intermediate_region_name", "checked_on", "source_url",
]


def build() -> int:
    # This one-time reference lookup is explicitly approved with a plain project UA.
    response = httpx.get(URL, timeout=10, headers={"User-Agent": "CS Jobs Research Dataset/2.0"})
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    table = soup.find("table")
    if table is None:
        raise RuntimeError("Official UN M49 page did not contain its expected table")
    rows = []
    seen = set()
    for row in table.select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
        if len(cells) < 12:
            continue
        # Columns: global code/name, region code/name, subregion code/name,
        # intermediate region code/name, country/area, M49, ISO alpha-2/3.
        country, m49, alpha2, alpha3 = cells[8:12]
        if len(alpha2) != 2 or not alpha2.isascii() or not alpha2.isalpha() or alpha2 in seen:
            continue
        seen.add(alpha2)
        rows.append({
            "country_or_area": country,
            "m49_code": m49,
            "iso_alpha2": alpha2,
            "iso_alpha3": alpha3,
            "region_code": cells[2],
            "region_name": cells[3],
            "subregion_code": cells[4],
            "subregion_name": cells[5],
            "intermediate_region_code": cells[6],
            "intermediate_region_name": cells[7],
            "checked_on": date.today().isoformat(),
            "source_url": URL,
        })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    print(f"Wrote {build()} ISO alpha-2 mappings to {OUTPUT}")
