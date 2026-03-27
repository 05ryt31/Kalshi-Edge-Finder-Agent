from datetime import date

from src.utils.ticker_parser import (
    ClimateTickerInfo,
    get_city_display_name,
    get_nws_station,
    parse_climate_ticker,
)


class TestParseClimateTicker:
    def test_high_temp_between(self):
        result = parse_climate_ticker("KXHIGHNY-26FEB22-B38.5")
        assert result is not None
        assert result.market_type == "high_temp"
        assert result.city_code == "NY"
        assert result.event_date == date(2022, 2, 26)
        assert result.threshold == 38.5
        assert result.bracket_type == "between"

    def test_high_temp_under(self):
        result = parse_climate_ticker("KXHIGHNY-26FEB22-T38")
        assert result is not None
        assert result.market_type == "high_temp"
        assert result.threshold == 38.0
        assert result.bracket_type == "under"

    def test_high_temp_above_equal(self):
        result = parse_climate_ticker("KXHIGHLAX-10MAR26-A75")
        assert result is not None
        assert result.market_type == "high_temp"
        assert result.city_code in ("LAX", "LA")
        assert result.threshold == 75.0
        assert result.bracket_type == "above_equal"

    def test_low_temp(self):
        result = parse_climate_ticker("KXLOWCHI-15JAN26-B20")
        assert result is not None
        assert result.market_type == "low_temp"
        assert result.city_code == "CHI"
        assert result.threshold == 20.0

    def test_snow_directional_threshold(self):
        result = parse_climate_ticker("KXSNOWSTORM-26FEBNYC2-15.0")
        assert result is not None
        assert result.market_type == "snow"
        assert result.city_code == "NYC"
        assert result.threshold == 15.0  # actual inches, no scaling
        assert result.bracket_type == "above_equal"

    def test_snow_alternate_format(self):
        result = parse_climate_ticker("KXNYCSNOWM-26FEB-6.0")
        assert result is not None
        assert result.market_type == "snow"
        assert result.city_code == "NYC"
        assert result.threshold == 6.0  # actual inches, no scaling
        assert result.bracket_type == "above_equal"

    def test_snow_with_between_prefix(self):
        result = parse_climate_ticker("KXNYCSNOWM-26FEB-B6.0")
        assert result is not None
        assert result.market_type == "snow"
        assert result.threshold == 6.0
        assert result.bracket_type == "between"

    def test_rain_ticker(self):
        result = parse_climate_ticker("KXRAINMIA-05MAR26-B10")
        assert result is not None
        assert result.market_type == "rain"
        assert result.city_code == "MIA"

    def test_four_digit_year(self):
        result = parse_climate_ticker("KXHIGHNY-26FEB2026-B40")
        assert result is not None
        assert result.event_date == date(2026, 2, 26)

    def test_no_date(self):
        result = parse_climate_ticker("KXHIGHNY-B40")
        assert result is not None
        assert result.event_date is None
        assert result.threshold == 40.0

    def test_non_climate_ticker_returns_none(self):
        assert parse_climate_ticker("NBA-LAKERS-ML") is None

    def test_empty_ticker_returns_none(self):
        assert parse_climate_ticker("") is None

    def test_no_city_returns_none(self):
        assert parse_climate_ticker("KXHIGH-26FEB22-B38") is None

    def test_no_threshold_returns_none(self):
        assert parse_climate_ticker("KXHIGHNY-26FEB22") is None

    def test_frozen_model(self):
        result = parse_climate_ticker("KXHIGHNY-26FEB22-B38.5")
        assert isinstance(result, ClimateTickerInfo)
        # Should be frozen (immutable)
        try:
            result.threshold = 99.0  # type: ignore[misc]
            assert False, "Should have raised"
        except Exception:
            pass

    def test_denver_station(self):
        result = parse_climate_ticker("KXHIGHDEN-01MAR26-B55")
        assert result is not None
        assert result.city_code == "DEN"


class TestGetNWSStation:
    def test_ny(self):
        assert get_nws_station("NY") == "KNYC"

    def test_nyc(self):
        assert get_nws_station("NYC") == "KNYC"

    def test_lax(self):
        assert get_nws_station("LAX") == "KLAX"

    def test_chi(self):
        assert get_nws_station("CHI") == "KORD"

    def test_unknown(self):
        assert get_nws_station("ZZZZZ") is None

    def test_case_insensitive(self):
        assert get_nws_station("ny") == "KNYC"


class TestGetCityDisplayName:
    def test_ny(self):
        assert get_city_display_name("NY") == "New York"

    def test_lax(self):
        assert get_city_display_name("LAX") == "Los Angeles"

    def test_unknown(self):
        assert get_city_display_name("ZZZZZ") is None
