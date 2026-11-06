from app.v2.geography import m49_region_for_country


def test_un_m49_region_lookup_uses_official_top_level_regions():
    assert m49_region_for_country("DE") == "150"  # Europe
    assert m49_region_for_country("US") == "019"  # Americas (UN M49 as-is)
    assert m49_region_for_country("KE") == "002"  # Africa
    assert m49_region_for_country("JP") == "142"  # Asia


def test_un_m49_lookup_is_case_insensitive():
    assert m49_region_for_country("de") == "150"
