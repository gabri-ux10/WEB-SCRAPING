import re


def parse_salary(raw: str | None) -> dict:
    if not raw:
        return {
            "salary_min": None,
            "salary_max": None,
            "salary_currency": None,
            "salary_period": None,
            "salary_raw": None,
        }
    matches = re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*([kKmM]?)", raw)
    vals = [
        float(number.replace(",", ""))
        * (1_000 if suffix.lower() == "k" else 1_000_000 if suffix.lower() == "m" else 1)
        for number, suffix in matches
    ]
    curr = next(
        (c for c in ("USD", "KES", "GBP", "EUR", "NGN", "ZAR", "CAD", "AUD") if c in raw.upper()),
        None,
    )
    low = raw.lower()
    period = next(
        (
            canonical
            for marker, canonical in (
                ("year", "year"),
                ("annual", "year"),
                ("month", "month"),
                ("weekly", "week"),
                ("week", "week"),
                ("day", "day"),
                ("hour", "hour"),
            )
            if marker in low
        ),
        None,
    )
    return {
        "salary_min": vals[0] if vals else None,
        "salary_max": vals[1] if len(vals) > 1 else None,
        "salary_currency": curr,
        "salary_period": period,
        "salary_raw": raw,
    }
