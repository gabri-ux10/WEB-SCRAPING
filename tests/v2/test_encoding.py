import unicodedata

from app.v2.encoding import assert_storable_title, decode_response


def test_http_charset_precedes_other_hints():
    decoded = decode_response(bytes([99, 97, 102, 233]), "text/plain; charset=iso-8859-1")
    assert decoded.text == "café"
    assert decoded.source_charset.lower() == "iso-8859-1"
    assert decoded.raw_bytes == bytes([99, 97, 102, 233])


def test_xml_declaration_is_used_when_header_has_no_charset():
    raw = b'<?xml version="1.0" encoding="Shift_JIS"?><feed/>'
    decoded = decode_response(raw, "application/xml")
    assert decoded.source_charset.lower().replace("-", "_") == "shift_jis"


def test_html_meta_charset_is_used_when_header_has_no_charset():
    raw = b'<html><head><meta charset="windows-1252"></head></html>'
    decoded = decode_response(raw, "text/html")
    assert decoded.source_charset.lower() == "windows-1252"


def test_json_is_utf8_even_if_header_claims_another_charset():
    raw = b'{"title":"caf\xc3\xa9"}'
    decoded = decode_response(raw, "application/json; charset=iso-8859-1")
    assert decoded.source_charset == "utf-8"
    assert "café" in decoded.text


def test_corrupted_title_is_rejected_before_storage():
    import pytest

    with pytest.raises(ValueError, match=r"U\+FFFD"):
        assert_storable_title("Développeur �")


def test_unicode_cleanup_nfc_controls_zero_width_and_nbsp():
    raw_text = "e\u0301\u00a0Engineer\x00\u200b\u202e"
    decoded = decode_response(raw_text.encode("utf-8"), "application/json")
    assert decoded.text == "é Engineer"
    assert unicodedata.is_normalized("NFC", decoded.text)


def test_response_bytes_are_preserved_for_redo():
    raw = b'{"title":"Engineer"}'
    decoded = decode_response(raw, "application/json")
    assert decoded.raw_bytes is raw
