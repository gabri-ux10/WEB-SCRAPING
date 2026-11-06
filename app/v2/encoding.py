from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from email.message import Message

from charset_normalizer import from_bytes

log = logging.getLogger(__name__)

_XML_ENCODING = re.compile(br"<\?xml[^>]*encoding\s*=\s*['\"]([^'\"]+)", re.I)
_HTML_CHARSET = re.compile(
    br"<meta[^>]+(?:charset\s*=\s*['\"]?\s*|content\s*=\s*['\"][^'\"]*?charset=)([\w.-]+)",
    re.I,
)
_ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"}


@dataclass(frozen=True)
class DecodedPayload:
    text: str
    source_charset: str
    raw_bytes: bytes
    mojibake_repaired: bool = False


def _declared_charset(raw: bytes, media_type: str) -> str | None:
    if media_type in {"application/xml", "text/xml", "application/rss+xml"} or media_type.endswith("+xml"):
        match = _XML_ENCODING.search(raw[:1024])
        if match:
            return match.group(1).decode("ascii", "ignore").strip()
    if media_type in {"text/html", "application/xhtml+xml"}:
        match = _HTML_CHARSET.search(raw[:8192])
        if match:
            return match.group(1).decode("ascii", "ignore").strip()
    return None


def _clean_unicode(text: str) -> str:
    text = unicodedata.normalize("NFC", text.replace("\u00a0", " "))
    return "".join(
        ch for ch in text
        if ch not in _ZERO_WIDTH and (ch in "\n\r\t" or unicodedata.category(ch) not in {"Cc", "Cf"})
    )


def assert_storable_title(title: str) -> str:
    """Reject titles with decode replacement markers instead of persisting corruption."""
    if "\ufffd" in title:
        raise ValueError("title contains U+FFFD and must be quarantined for review")
    return title


def _repair_mojibake(text: str) -> tuple[str, bool]:
    try:
        from ftfy import fix_text
    except ImportError:
        return text, False
    fixed = fix_text(text)
    return fixed, fixed != text


def decode_response(
    raw: bytes,
    content_type: str | None = None,
    *,
    media_type: str | None = None,
) -> DecodedPayload:
    """Decode original response bytes in the order defined by the v2 spec."""
    if not isinstance(raw, bytes):
        raise TypeError("raw response must be bytes")
    header = content_type or ""
    media = (media_type or header.partition(";")[0]).strip().lower()
    json_media = media == "application/json" or media.endswith("+json")
    if json_media:
        charset = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
        text = raw.decode(charset, errors="strict")
    else:
        header_message = Message()
        if header:
            header_message["content-type"] = header
        declared_charset = header_message.get_content_charset()
        candidates = []
        if declared_charset:
            candidates.append(declared_charset.strip())
        xml_or_meta = _declared_charset(raw, media)
        if xml_or_meta:
            candidates.append(xml_or_meta)
        text = None
        charset = ""
        for candidate in candidates:
            try:
                text = raw.decode(candidate, errors="strict")
                charset = candidate
                break
            except (LookupError, UnicodeDecodeError):
                continue
        if text is None:
            match = from_bytes(raw).best()
            if match is None or not match.encoding:
                raise UnicodeError("charset-normalizer could not detect the response charset")
            charset = match.encoding
            text = str(match)
    text = _clean_unicode(text)
    # Running text repair over serialized JSON can change punctuation inside
    # string values and make the document invalid. Repair JSON fields after
    # parsing instead of rewriting its syntax.
    if json_media:
        repaired = False
    else:
        text, repaired = _repair_mojibake(text)
    if repaired:
        log.info("ftfy repaired mojibake in a captured response")
    return DecodedPayload(text, charset, raw, repaired)


def parse_json_payload(payload: DecodedPayload):
    """Parse JSON only after byte-first decoding; JSON must be UTF-8."""
    return json.loads(payload.text)
