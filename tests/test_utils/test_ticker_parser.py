from datetime import date

from src.utils.ticker_parser import (
    ClimateTickerInfo,
    get_city_display_name,
    get_nws_station,
    parse_climate_ticker,
    parse_ticker_date,
)


class TestParseClimateTicker:
    def test_high_temp_between(self):
        # YYMMMDD: 26FEB22 → year=2026, day=22
        result = parse_climate_ticker("KXHIGHNY-26FEB22-B38.5")
        assert result is not None
        assert result.market_type == "high_temp"
        assert result.city_code == "NY"
        assert result.event_date == date(2026, 2, 22)
        assert result.threshold == 38.5
        assert result.bracket_type == "between"

    def test_high_temp_under(self):
        result = parse_climate_ticker("KXHIGHNY-26FEB22-T38")
        assert result is not None
        assert result.market_type == "high_temp"
        assert result.threshold == 38.0
        assert result.bracket_type == "under"

    def test_high_temp_above_equal(self):
        # YYMMMDD: 26MAR10 → year=2026, day=10
        result = parse_climate_ticker("KXHIGHLAX-26MAR10-A75")
        assert result is not None
        assert result.market_type == "high_temp"
        assert result.city_code in ("LAX", "LA")
        assert result.event_date == date(2026, 3, 10)
        assert result.threshold == 75.0
        assert result.bracket_type == "above_equal"

    def test_low_temp(self):
        # YYMMMDD: 26JAN15 → year=2026, day=15
        result = parse_climate_ticker("KXLOWCHI-26JAN15-B20")
        assert result is not None
        assert result.market_type == "low_temp"
        assert result.city_code == "CHI"
        assert result.event_date == date(2026, 1, 15)
        assert result.threshold == 20.0

    def test_snow_directional_threshold(self):
        result = parse_climate_ticker("KXSNOWSTORM-26FEBNYC2-15.0")
        assert result is not None
        assert result.market_type == "snow"
        assert result.city_code == "NYC"
        assert result.threshold == 15.0
        assert result.bracket_type == "above_equal"

    def test_snow_alternate_format(self):
        result = parse_climate_ticker("KXNYCSNOWM-26FEB-6.0")
        assert result is not None
        assert result.market_type == "snow"
        assert result.city_code == "NYC"
        assert result.threshold == 6.0
        assert result.bracket_type == "above_equal"

    def test_snow_with_between_prefix(self):
        result = parse_climate_ticker("KXNYCSNOWM-26FEB-B6.0")
        assert result is not None
        assert result.market_type == "snow"
        assert result.threshold == 6.0
        assert result.bracket_type == "between"

    def test_rain_ticker(self):
        # YYMMMDD: 26MAR05 → year=2026, day=5
        result = parse_climate_ticker("KXRAINMIA-26MAR05-B10")
        assert result is not None
        assert result.market_type == "rain"
        assert result.city_code == "MIA"
        assert result.event_date == date(2026, 3, 5)

    def test_four_digit_year(self):
        # DDMMMYYYY: 22FEB2026 → day=22, year=2026
        result = parse_climate_ticker("KXHIGHNY-22FEB2026-B40")
        assert result is not None
        assert result.event_date == date(2026, 2, 22)

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
        try:
            result.threshold = 99.0  # type: ignore[misc]
            assert False, "Should have raised"
        except Exception:
            pass

    def test_denver_station(self):
        result = parse_climate_ticker("KXHIGHDEN-26MAR01-B55")
        assert result is not None
        assert result.city_code == "DEN"
        assert result.event_date == date(2026, 3, 1)


class TestParseTickerDate:
    def test_climate_ticker(self):
        assert parse_ticker_date("KXHIGHNY-26FEB22-B38.5") == date(2026, 2, 22)

    def test_dota_ticker(self):
        assert parse_ticker_date("KXDOTA2GAME-26FEB16AURBB-BB") == date(2026, 2, 16)

    def test_sports_ticker_with_date(self):
        assert parse_ticker_date("KXNBA-26MAR05-SPREAD") == date(2026, 3, 5)

    def test_no_date_in_ticker(self):
        assert parse_ticker_date("NBA-LAKERS-ML") is None

    def test_empty_ticker(self):
        assert parse_ticker_date("") is None

    def test_four_digit_year(self):
        assert parse_ticker_date("SOME-22FEB2026-THING") == date(2026, 2, 22)


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
