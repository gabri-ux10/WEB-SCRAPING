def normalize_title(title: str | None) -> str | None:
    return " ".join((title or "").lower().split()) or None
