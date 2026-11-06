from datetime import UTC

from scripts.run_stage2_europe_pilot import (
    _country, _date, _json_array_record_bytes, _location, _work_modes, _xml_item_bytes,
)


def test_country_resolves_iso_codes_and_common_official_names():
    assert _country("DE") == "DE"
    assert _country("Germany") == "DE"
    assert _country("UK") == "GB"
    assert _country("United States") == "US"
    assert _country("Europe") is None


def test_location_requires_country_evidence():
    assert _location("Berlin, Germany") == ("Berlin", "DE")
    assert _location("Remote, Europe") == ("Remote", None)


def test_exact_json_record_bytes_are_extracted_from_utf8_payload():
    raw = '{"data":[{"title":"Développeur"},{"title":"Engineer"}],"meta":{}}'.encode("utf-8")
    records = _json_array_record_bytes(raw, "data")
    assert records == ['{"title":"Développeur"}'.encode(), b'{"title":"Engineer"}']


def test_xml_items_are_captured_individually():
    raw = b'<rss><channel><item><title>A</title></item><item><title>B</title></item></channel></rss>'
    assert _xml_item_bytes(raw) == [b'<item><title>A</title></item>', b'<item><title>B</title></item>']


def test_dates_parse_epoch_iso_and_rfc822():
    assert _date(0).tzinfo == UTC
    assert _date("2026-11-06T12:00:00Z").year == 2026
    assert _date("Fri, 06 Nov 2026 12:00:00 GMT").year == 2026


def test_teamtailor_remote_status_is_not_truthiness_coerced():
    assert _work_modes("none") == (False, False)
    assert _work_modes("fully") == (True, False)
    assert _work_modes("hybrid") == (False, True)
