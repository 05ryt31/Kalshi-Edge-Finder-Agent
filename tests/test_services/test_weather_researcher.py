from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.clients.nws import ASOSObservation, DailyCLI, NWSClient
from src.clients.openweather import OpenWeatherClient
from src.schemas.market import Market
from src.services.research.weather import WeatherResearcher
from src.utils.ticker_parser import ClimateTickerInfo


def _make_market(
    ticker="KXHIGHNY-26FEB22-B38.5",
    title="NYC High Temp",
    category="climate",
    climate_info=None,
    yes_ask=50,
    ticker_date=None,
) -> Market:
    return Market(
        ticker=ticker,
        event_ticker="KXHIGH",
        title=title,
        subtitle=None,
        category=category,
        status="open",
        yes_ask=yes_ask,
        no_ask=100 - yes_ask,
        yes_bid=yes_ask - 2,
        no_bid=100 - yes_ask - 2,
        last_price=yes_ask,
        volume=1000,
        volume_24h=500,
        close_time=datetime(2026, 2, 22, 23, 59, tzinfo=timezone.utc),
        expiration_time=datetime(2026, 2, 22, 23, 59, tzinfo=timezone.utc),
        climate_info=climate_info,
        ticker_date=ticker_date,
    )


def _make_climate_info(
    market_type="high_temp",
    city_code="NY",
    event_date=None,
    threshold=38.5,
    bracket_type="between",
) -> ClimateTickerInfo:
    return ClimateTickerInfo(
        market_type=market_type,
        city_code=city_code,
        event_date=event_date,
        threshold=threshold,
        bracket_type=bracket_type,
    )


def _make_observations(temps: list[float], station: str = "KNYC") -> list[ASOSObservation]:
    return [
        ASOSObservation(
            station=station,
            valid_time=f"2026-02-22 {10 + i}:00",
            temp_f=t,
            dwpf=None,
            sknt=None,
            precip_in=None,
        )
        for i, t in enumerate(temps)
    ]


class TestWeatherResearcherNWSPath:
    @pytest.mark.asyncio
    async def test_nws_grounded_with_observations(self):
        nws = AsyncMock(spec=NWSClient)
        nws.get_observations.return_value = _make_observations([35.0, 38.0, 40.5])
        nws.get_daily_cli.return_value = None
        nws.get_nws_latest_observation.return_value = None

        ow = AsyncMock(spec=OpenWeatherClient)
        ow.get_forecast.return_value = {"list": []}

        climate_info = _make_climate_info(event_date=date(2099, 1, 1))  # future
        market = _make_market(climate_info=climate_info)
        researcher = WeatherResearcher(ow, nws)
        result = await researcher.research(market)

        assert result["category"] == "climate"
        assert "NWS ASOS" in result["data_sources"]
        assert result["collected_data"]["running_daily_high_f"] == 40.5
        assert result["collected_data"]["running_daily_low_f"] == 35.0
        assert result["collected_data"]["nws_station"] == "KNYC"

    @pytest.mark.asyncio
    async def test_day_of_fetches_cli(self):
        nws = AsyncMock(spec=NWSClient)
        nws.get_observations.return_value = _make_observations([38.0, 42.0])
        nws.get_daily_cli.return_value = DailyCLI(
            station="KNYC",
            report_date=date.today(),
            high_temp=42.0,
            low_temp=30.0,
            precip=0.0,
            snow=None,
        )
        nws.get_nws_latest_observation.return_value = None

        ow = AsyncMock(spec=OpenWeatherClient)

        climate_info = _make_climate_info(event_date=date.today())
        market = _make_market(climate_info=climate_info)
        researcher = WeatherResearcher(ow, nws)
        result = await researcher.research(market)

        assert "NWS CLI Report" in result["data_sources"]
        assert result["collected_data"]["cli_high"] == 42.0
        assert result["collected_data"]["is_day_of_event"] is True
        # Day-of should NOT call OpenWeather forecast
        ow.get_forecast.assert_not_called()

    @pytest.mark.asyncio
    async def test_future_event_uses_openweather_forecast(self):
        nws = AsyncMock(spec=NWSClient)
        nws.get_observations.return_value = _make_observations([35.0])
        nws.get_daily_cli.return_value = None
        nws.get_nws_latest_observation.return_value = None

        ow = AsyncMock(spec=OpenWeatherClient)
        ow.get_forecast.return_value = {
            "list": [
                {"dt_txt": "2026-02-23 12:00", "main": {"temp": 50.0}, "weather": [{"description": "clear"}]},
            ]
        }

        climate_info = _make_climate_info(event_date=date(2099, 3, 1))
        market = _make_market(climate_info=climate_info)
        researcher = WeatherResearcher(ow, nws)
        result = await researcher.research(market)

        assert "OpenWeatherMap" in result["data_sources"]
        assert len(result["collected_data"]["forecast"]) == 1

    @pytest.mark.asyncio
    async def test_nws_failure_graceful_degradation(self):
        nws = AsyncMock(spec=NWSClient)
        nws.get_observations.return_value = []  # empty
        nws.get_daily_cli.return_value = None
        nws.get_nws_latest_observation.return_value = {"temperature_f": 37.0, "description": "cloudy"}

        ow = AsyncMock(spec=OpenWeatherClient)
        ow.get_forecast.return_value = {"list": []}

        climate_info = _make_climate_info(event_date=date(2099, 3, 1))
        market = _make_market(climate_info=climate_info)
        researcher = WeatherResearcher(ow, nws)
        result = await researcher.research(market)

        assert "NWS Latest Observation" in result["data_sources"]
        assert result["collected_data"]["nws_latest"]["temperature_f"] == 37.0

    @pytest.mark.asyncio
    async def test_resolution_criteria_in_collected_data(self):
        nws = AsyncMock(spec=NWSClient)
        nws.get_observations.return_value = _make_observations([40.0])
        nws.get_daily_cli.return_value = None
        nws.get_nws_latest_observation.return_value = None

        ow = AsyncMock(spec=OpenWeatherClient)
        ow.get_forecast.return_value = {"list": []}

        climate_info = _make_climate_info(event_date=date(2099, 3, 1))
        market = _make_market(climate_info=climate_info, title="Will the high temp in NYC be >40?")
        researcher = WeatherResearcher(ow, nws)
        result = await researcher.research(market)

        criteria = result["collected_data"]["resolution_criteria"]
        assert "official daily high temperature" in criteria
        assert "Market question (from title):" in criteria
        assert "WARNING" in criteria

    @pytest.mark.asyncio
    async def test_summary_contains_station(self):
        nws = AsyncMock(spec=NWSClient)
        nws.get_observations.return_value = _make_observations([35.0, 40.0])
        nws.get_daily_cli.return_value = None
        nws.get_nws_latest_observation.return_value = None

        ow = AsyncMock(spec=OpenWeatherClient)
        ow.get_forecast.return_value = {"list": []}

        climate_info = _make_climate_info(event_date=date(2099, 3, 1))
        market = _make_market(climate_info=climate_info)
        researcher = WeatherResearcher(ow, nws)
        result = await researcher.research(market)

        assert "KNYC" in result["summary"]


class TestWeatherResearcherLegacyPath:
    @pytest.mark.asyncio
    async def test_legacy_path_no_climate_info(self):
        nws = AsyncMock(spec=NWSClient)
        ow = AsyncMock(spec=OpenWeatherClient)
        ow.get_forecast.return_value = {
            "list": [
                {"dt_txt": "2026-02-22 12:00", "main": {"temp": 45.0}, "weather": [{"description": "clear"}]},
            ]
        }
        ow.get_current.return_value = {
            "main": {"temp": 40.0},
            "weather": [{"description": "overcast"}],
        }

        market = _make_market(title="NYC max temperature today", climate_info=None)
        researcher = WeatherResearcher(ow, nws)
        result = await researcher.research(market)

        assert "OpenWeatherMap" in result["data_sources"]
        assert result["collected_data"]["current_temp"] == 40.0

    @pytest.mark.asyncio
    async def test_legacy_path_no_nws_client(self):
        ow = AsyncMock(spec=OpenWeatherClient)
        ow.get_forecast.return_value = {
            "list": [
                {"dt_txt": "2026-02-22 12:00", "main": {"temp": 50.0}, "weather": [{"description": "sunny"}]},
            ]
        }
        ow.get_current.return_value = {
            "main": {"temp": 48.0},
            "weather": [{"description": "clear sky"}],
        }

        climate_info = _make_climate_info(event_date=date(2099, 3, 1))
        market = _make_market(title="NYC High Temp", climate_info=climate_info)
        # NWS client is None → falls through to legacy
        researcher = WeatherResearcher(ow, nws=None)
        result = await researcher.research(market)

        # Without NWS, climate_info+None NWS should use legacy
        # Actually with our implementation, climate_info AND nws both needed for NWS path
        assert "OpenWeatherMap" in result["data_sources"]

    @pytest.mark.asyncio
    async def test_legacy_city_not_found(self):
        ow = AsyncMock(spec=OpenWeatherClient)
        market = _make_market(title="Some random event here", climate_info=None)
        researcher = WeatherResearcher(ow, nws=None)
        result = await researcher.research(market)

        assert result["data_sources"] == []
        assert "Could not extract city" in result["summary"]

    @pytest.mark.asyncio
    async def test_legacy_api_error(self):
        ow = AsyncMock(spec=OpenWeatherClient)
        ow.get_forecast.side_effect = Exception("API error")
        ow.get_current.side_effect = Exception("API error")

        market = _make_market(title="NYC temperature", climate_info=None)
        researcher = WeatherResearcher(ow, nws=None)
        result = await researcher.research(market)

        assert result["data_sources"] == []
        assert "Error" in result["summary"]


class TestWeatherResearcherConcludedEvent:
    @pytest.mark.asyncio
    async def test_concluded_event_cli_only(self):
        """Concluded event should only fetch CLI, no ASOS or OpenWeather."""
        nws = AsyncMock(spec=NWSClient)
        nws.get_daily_cli.return_value = DailyCLI(
            station="CLINYC",
            report_date=date(2026, 2, 21),
            high_temp=35.0,
            low_temp=28.0,
            precip=0.5,
            snow=2.0,
        )

        ow = AsyncMock(spec=OpenWeatherClient)

        climate_info = _make_climate_info(event_date=date(2026, 2, 21))
        market = _make_market(climate_info=climate_info, ticker_date=date(2026, 2, 21))
        researcher = WeatherResearcher(ow, nws)
        result = await researcher.research(market)

        assert result["collected_data"]["event_concluded"] is True
        assert result["collected_data"]["official_data_missing"] is False
        assert result["collected_data"]["cli_high"] == 35.0
        assert "CONCLUDED EVENT" in result["summary"]
        assert "NWS CLI Report" in result["data_sources"]
        # Should NOT call ASOS or OpenWeather
        nws.get_observations.assert_not_called()
        ow.get_forecast.assert_not_called()

    @pytest.mark.asyncio
    async def test_concluded_event_missing_cli(self):
        """Concluded event with no CLI data should flag official_data_missing."""
        nws = AsyncMock(spec=NWSClient)
        nws.get_daily_cli.return_value = None

        ow = AsyncMock(spec=OpenWeatherClient)

        climate_info = _make_climate_info(event_date=date(2026, 2, 21))
        market = _make_market(climate_info=climate_info, ticker_date=date(2026, 2, 21))
        researcher = WeatherResearcher(ow, nws)
        result = await researcher.research(market)

        assert result["collected_data"]["event_concluded"] is True
        assert result["collected_data"]["official_data_missing"] is True
        assert "MISSING" in result["summary"]
        nws.get_observations.assert_not_called()
        ow.get_forecast.assert_not_called()
