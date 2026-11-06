from __future__ import annotations

import hashlib
import json
import os

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.v2.database import TranslationCache
from app.v2.taxonomy import load_taxonomy


class LLMConfigurationError(RuntimeError):
    pass


class OpenAICompatibleLLM:
    """Optional JSON-mode client. No request is sent until all settings are supplied."""

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("V2_LLM_API_KEY")
        self.base_url = (base_url or os.getenv("V2_LLM_BASE_URL") or "").rstrip("/")
        self.model = model or os.getenv("V2_LLM_MODEL")
        if not all((self.api_key, self.base_url, self.model)):
            raise LLMConfigurationError("Set V2_LLM_API_KEY, V2_LLM_BASE_URL, and V2_LLM_MODEL to enable LLM calls")

    async def json_completion(self, prompt: str) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}},
            )
            response.raise_for_status()
        return json.loads(response.json()["choices"][0]["message"]["content"])


def title_cache_key(title: str, target_language: str = "en") -> str:
    return hashlib.sha256(f"{target_language}\0{title.strip()}".encode("utf-8")).hexdigest()


async def translate_title(
    title: str,
    source_language: str,
    session: AsyncSession,
    llm: OpenAICompatibleLLM,
) -> tuple[str, str]:
    key = title_cache_key(title)
    cached = (await session.execute(select(TranslationCache).where(
        TranslationCache.title_hash == key, TranslationCache.target_language == "en"
    ))).scalar_one_or_none()
    if cached:
        return cached.translated_title, cached.translation_method
    result = await llm.json_completion(
        "Translate the following job title into English only. Keep seniority and technical meaning. "
        "Return JSON with a single string field translated_title. Do not translate any description.\n"
        f"Source language: {source_language}\nTitle: {title}"
    )
    translated = result.get("translated_title")
    if not isinstance(translated, str) or not translated.strip() or "\ufffd" in translated:
        raise ValueError("LLM returned an invalid English job title translation")
    row = TranslationCache(title_hash=key, source_title=title, target_language="en", translated_title=translated.strip(), translation_method="llm", model=llm.model)
    session.add(row)
    await session.flush()
    return row.translated_title, row.translation_method


async def classify_title_with_llm(
    title: str,
    skills: list[str],
    llm: OpenAICompatibleLLM,
    *,
    taxonomy_path=None,
) -> dict | None:
    taxonomy = load_taxonomy(taxonomy_path) if taxonomy_path else load_taxonomy()
    allowed = [{"category_id": c["id"], "category": c["name"], "subdomains": [{"sub_domain_id": s["id"], "sub_domain": s["name"]} for s in c["subdomains"]]} for c in taxonomy["categories"]]
    prompt = (
        "Classify this ambiguous job title using only the supplied taxonomy. Do not infer from employer. "
        "Use skills only when title is ambiguous. Return JSON fields category_id, sub_domain_id, "
        "role_confidence, reason_code. Use category_id U and sub_domain_id null when uncertain.\n"
        f"TAXONOMY={json.dumps(allowed, ensure_ascii=False)}\nTITLE={title}\nSKILLS={json.dumps(skills, ensure_ascii=False)}"
    )
    allowed_ids = {s["id"] for c in taxonomy["categories"] for s in c["subdomains"]}
    for attempt in range(2):
        result = await llm.json_completion(prompt)
        confidence = result.get("role_confidence")
        if (
            result.get("sub_domain_id") in allowed_ids
            and isinstance(confidence, (int, float))
            and 0.70 <= confidence <= 1
        ):
            return result
        if attempt == 0:
            prompt += "\nYour previous response failed validation. Return a corrected JSON object using only valid taxonomy IDs, or U/null if uncertain."
    return None
