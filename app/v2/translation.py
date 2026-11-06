"""Offline Helsinki-NLP OPUS-MT title translation; models must be pre-cached."""

from __future__ import annotations

from functools import lru_cache
import argparse
import csv
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("HF_HOME", str(ROOT / "models" / "hf"))

MODEL_IDS = {
    language: f"Helsinki-NLP/opus-mt-{language}-en"
    for language in ("de", "fr", "es", "pt", "it", "nl", "ja", "zh")
}
SMOKE_TITLES = {
    "de": "Softwareentwickler", "fr": "Ingénieur logiciel", "es": "Ingeniero de software",
    "pt": "Engenheiro de software", "it": "Ingegnere software", "nl": "Softwareontwikkelaar",
    "ja": "ソフトウェアエンジニア", "zh": "软件工程师",
}


@lru_cache(maxsize=8)
def _load_model(language: str):
    if language not in MODEL_IDS:
        raise ValueError(f"No configured OPUS-MT model for language {language!r}")
    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        import torch
    except ImportError as exc:
        raise RuntimeError("Install the translation extra before running the pilot") from exc
    model_id = MODEL_IDS[language]
    tokenizer = AutoTokenizer.from_pretrained(model_id, local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_id, local_files_only=True)
    model.eval()
    return tokenizer, model, torch


def translate_title(title: str, language: str) -> str | None:
    """Translate a title locally; never sends title text to an external service."""
    if language == "en":
        return title
    if language not in MODEL_IDS:
        return None
    tokenizer, model, torch = _load_model(language)
    inputs = tokenizer(title, return_tensors="pt", truncation=True, max_length=128)
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=64, num_beams=4)
    result = tokenizer.decode(output[0], skip_special_tokens=True).strip()
    if not result or "\ufffd" in result:
        return None
    return result


def preflight_models() -> dict[str, str]:
    """Run one short local inference for each configured language before any scrape."""
    outputs = {}
    for language, title in SMOKE_TITLES.items():
        translated = translate_title(title, language)
        if not translated:
            raise RuntimeError(f"Local OPUS-MT preflight returned an empty translation for {language}")
        outputs[language] = translated
    return outputs


def main() -> None:
    """Translate a CSV title column using only the local Hugging Face cache."""
    parser = argparse.ArgumentParser(prog="translate_titles")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--title-column", default="raw_title")
    parser.add_argument("--language-column", default="title_language")
    args = parser.parse_args()
    with args.input_csv.open(encoding="utf-8-sig", newline="") as src:
        reader = csv.DictReader(src)
        if not reader.fieldnames or args.title_column not in reader.fieldnames:
            raise SystemExit(f"Missing title column: {args.title_column}")
        fields = list(reader.fieldnames)
        for name in ("clean_title_en", "translation_method"):
            if name not in fields:
                fields.append(name)
        rows = list(reader)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            language = row.get(args.language_column, "") or "en"
            result = translate_title(row.get(args.title_column, ""), language)
            row["clean_title_en"] = result or ""
            row["translation_method"] = "opus_mt_local" if result and language != "en" else ("original_english" if result else "pending")
            writer.writerow(row)


if __name__ == "__main__":
    main()
