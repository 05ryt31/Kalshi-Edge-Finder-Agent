from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.clients.nws import ASOSObservation, DailyCLI, NWSClient, _parse_float


class TestParseFloat:
    def test_valid_float(self):
        assert _parse_float("72.5") == 72.5

    def test_missing_value(self):
        assert _parse_float("M") is None

    def test_trace_value(self):
        assert _parse_float("T") is None

    def test_empty_string(self):
        assert _parse_float("") is None

    def test_whitespace(self):
        assert _parse_float("  42.0  ") == 42.0

    def test_invalid_string(self):
        assert _parse_float("abc") is None


class TestASOSCSVParsing:
    def test_parse_asos_csv(self):
        csv_text = (
            "station,valid,tmpf,dwpf,sknt,p01i\n"
            "KNYC,2026-02-22 10:00,38.0,25.0,5.0,0.00\n"
            "KNYC,2026-02-22 11:00,40.5,26.0,7.0,0.00\n"
            "KNYC,2026-02-22 12:00,42.0,M,6.0,T\n"
        )
        client = NWSClient()
        observations = client._parse_asos_csv(csv_text, "KNYC")

        assert len(observations) == 3
        assert observations[0].station == "KNYC"
        assert observations[0].temp_f == 38.0
        assert observations[1].temp_f == 40.5
        assert observations[2].temp_f == 42.0
        assert observations[2].dwpf is None  # M value
        assert observations[2].precip_in is None  # T value

    def test_parse_empty_csv(self):
        client = NWSClient()
        observations = client._parse_asos_csv("station,valid,tmpf,dwpf,sknt,p01i\n", "KNYC")
        assert observations == []


class TestNWSClientCtoF:
    def test_freezing(self):
        assert NWSClient._c_to_f(0.0) == 32.0

    def test_boiling(self):
        assert NWSClient._c_to_f(100.0) == 212.0

    def test_none(self):
        assert NWSClient._c_to_f(None) is None


class TestNWSClientGetObservations:
    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        client = NWSClient()
        client.client = AsyncMock()
        client.client.get = AsyncMock(side_effect=Exception("network error"))
        result = await client.get_observations("KNYC", hours=24)
        assert result == []
        await client.close()


class TestNWSClientGetDailyCLI:
    @pytest.mark.asyncio
    async def test_returns_none_on_error(self):
        client = NWSClient()
        client.client = AsyncMock()
        client.client.get = AsyncMock(side_effect=Exception("network error"))
        result = await client.get_daily_cli("KNYC", date(2026, 2, 22))
        assert result is None
        await client.close()

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_results(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"results": []}

        client = NWSClient()
        client.client = AsyncMock()
        client.client.get = AsyncMock(return_value=mock_response)

        result = await client.get_daily_cli("KNYC", date(2026, 2, 22))
        assert result is None
        await client.close()

    @pytest.mark.asyncio
    async def test_parses_cli_json(self):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "high": 45,
                    "low": 32,
                    "precip": 0.12,
                    "snow": "M",
                }
            ]
        }

        client = NWSClient()
        client.client = AsyncMock()
        client.client.get = AsyncMock(return_value=mock_response)

        result = await client.get_daily_cli("KNYC", date(2026, 2, 22))
        assert result is not None
        assert result.high_temp == 45.0
        assert result.low_temp == 32.0
        assert result.precip == 0.12
        assert result.snow is None  # "M" → None
        await client.close()


class TestNWSClientLatestObservation:
    @pytest.mark.asyncio
    async def test_returns_none_on_error(self):
        client = NWSClient()
        client.client = AsyncMock()
        client.client.get = AsyncMock(side_effect=Exception("network error"))
        result = await client.get_nws_latest_observation("KNYC")
        assert result is None
        await client.close()


class TestDailySummaries:
    def test_parse_daily_csv(self):
        csv_text = (
            "station,day,max_temp_f,min_temp_f,max_dewpoint_f,min_dewpoint_f,precip_in,"
            "avg_wind_speed_kts,avg_wind_drct,min_rh,avg_rh,max_rh,snow_in,snowd_in,"
            "min_feel,avg_feel,max_feel,max_wind_speed_kts,max_wind_gust_kts,srad_mj,"
            "climo_high_f,climo_low_f,climo_precip_in\n"
            "NYC,2024-07-01,81.0,64.0,,,0.03,,,,,,0.0,,,,,,,,,,\n"
            "NYC,2024-07-02,86.0,66.0,,,M,,,,,,T,,,,,,,,,,\n"
        )
        rows = NWSClient._parse_daily_csv(csv_text, "KNYC")
        assert len(rows) == 2
        assert rows[0].obs_date == date(2024, 7, 1)
        assert rows[0].high_temp_f == 81.0
        assert rows[0].low_temp_f == 64.0
        assert rows[0].precip_in == 0.03
        assert rows[0].snow_in == 0.0
        assert rows[1].precip_in is None  # 'M'
        assert rows[1].snow_in is None  # 'T'

    @pytest.mark.asyncio
    async def test_unknown_station_returns_empty(self):
        client = NWSClient()
        result = await client.get_daily_summaries(
            "KZZZ", date(2024, 1, 1), date(2024, 1, 5)
        )
        assert result == []
        await client.close()

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        client = NWSClient()
        client.client = AsyncMock()
        client.client.get = AsyncMock(side_effect=Exception("boom"))
        result = await client.get_daily_summaries(
            "KNYC", date(2024, 1, 1), date(2024, 1, 5)
        )
        assert result == []
        await client.close()
