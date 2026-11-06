from __future__ import annotations

import re
import unicodedata

_CUES = {
    "de": (" der ", " die ", " und ", " für ", "wir suchen", "aufgaben", "anforderungen", "entwickler", "unternehmen"),
    "fr": (" le ", " les ", " et ", " pour ", "nous recherchons", "expérience", "développeur"),
    "es": (" el ", " los ", " y ", " para ", "buscamos", "experiencia", "desarrollador"),
    "pt": (" o ", " os ", " e ", " para ", "procuramos", "experiência", "desenvolvedor"),
    "it": (" il ", " gli ", " e ", " per ", "cerchiamo", "esperienza", "sviluppatore"),
    "nl": (" het ", " een ", " en ", " voor ", "wij zoeken", "ervaring", "ontwikkelaar"),
    "ja": ("の", "です", "ます", "応募", "経験", "仕事内容"),
    "zh": ("的", "职位", "经验", "工作", "要求", "我们正在寻找"),
    "ko": ("의", "합니다", "경험", "지원", "모집", "담당업무"),
}
_SCRIPT_RANGES = {
    "ja": (0x3040, 0x30FF), "zh": (0x3400, 0x9FFF), "ko": (0xAC00, 0xD7AF),
}


def detect_language(text: str | None, locale_hint: str | None = None) -> tuple[str | None, float | None]:
    if not text or not text.strip():
        return None, None
    sample = " " + unicodedata.normalize("NFC", text[:12000]).lower() + " "
    scripts = {lang: sum(lo <= ord(ch) <= hi for ch in sample) for lang, (lo, hi) in _SCRIPT_RANGES.items()}
    script, count = max(scripts.items(), key=lambda item: item[1])
    if count >= max(2, len(sample) * 0.04):
        return script, min(0.99, 0.75 + count / max(len(sample), 1))
    scores = {lang: sum(sample.count(cue) for cue in cues) for lang, cues in _CUES.items()}
    language, score = max(scores.items(), key=lambda item: item[1])
    if score:
        return language, min(0.99, 0.55 + score * 0.06)
    if locale_hint and re.match(r"^[a-z]{2}(?:[-_][A-Z]{2})?$", locale_hint):
        return locale_hint[:2].lower(), 0.60
    return "en", 0.55


def detect_posting_languages(title: str, description: str | None, locale_hint: str | None = None) -> dict:
    title_language, title_confidence = detect_language(title, locale_hint)
    description_language, description_confidence = detect_language(description, locale_hint)
    return {
        "title_language": title_language or "und",
        "description_language": description_language,
        "language_confidence": description_confidence if description_confidence is not None else title_confidence,
    }
