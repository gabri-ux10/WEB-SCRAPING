COUNTRIES = {
    "kenya": "KE",
    "nigeria": "NG",
    "south africa": "ZA",
    "ghana": "GH",
    "uganda": "UG",
    "tanzania": "TZ",
    "rwanda": "RW",
    "ethiopia": "ET",
    "egypt": "EG",
    "morocco": "MA",
    "united states": "US",
    "usa": "US",
    "united kingdom": "GB",
    "uk": "GB",
}
CITIES = {
    "nairobi": "KE",
    "lagos": "NG",
    "johannesburg": "ZA",
    "accra": "GH",
    "kampala": "UG",
    "dar es salaam": "TZ",
    "kigali": "RW",
    "addis ababa": "ET",
    "cairo": "EG",
    "casablanca": "MA",
}


def normalize_location(
    raw: str | None, explicit_country: str | None = None, remote: str | None = None
) -> dict:
    text = (raw or "").strip()
    low = text.lower()
    code = None
    country = None
    city = None
    remote_type = (remote or "").lower()
    if not remote_type:
        remote_type = (
            "remote"
            if "remote" in low or "anywhere" in low
            else (
                "hybrid"
                if "hybrid" in low
                else "onsite"
                if "on-site" in low or "onsite" in low
                else "unknown"
            )
        )
    if remote_type not in {"remote", "hybrid", "onsite", "unknown"}:
        remote_type = "unknown"
    if explicit_country:
        country = explicit_country
        code = next(
            (c for n, c in COUNTRIES.items() if n == explicit_country.lower()),
            explicit_country.upper() if len(explicit_country) == 2 else None,
        )
    for cname, ccode in COUNTRIES.items():
        if cname in low:
            country = cname.title()
            code = ccode
            break
    for cname, ccode in CITIES.items():
        if cname in low:
            city = cname.title()
            code = code or ccode
            break
    if not country and code:
        country = next((k.title() for k, v in COUNTRIES.items() if v == code), None)
    # City-only matches identify a country only for this explicit small, well-known map.
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not city and parts and not any(term in parts[0].lower() for term in ("remote", "hybrid")):
        city = parts[0]
    region = parts[1] if len(parts) > 2 else None
    return {
        "location_raw": text or None,
        "city": city,
        "region": region,
        "country": country,
        "country_code": code,
        "remote_type": remote_type,
    }
