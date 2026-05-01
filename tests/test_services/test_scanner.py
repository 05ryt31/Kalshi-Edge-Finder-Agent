from datetime import date

from src.services.scanner import ScannerService
from src.utils.ticker_parser import ClimateTickerInfo


class TestScannerClimateInfo:
    def setup_method(self):
        self.scanner = ScannerService(None)

    def test_climate_market_gets_climate_info(self):
        data = {
            "ticker": "KXHIGHNY-26FEB22-B38.5",
            "event_ticker": "KXHIGH",
            "title": "NYC High Temperature",
            "close_time": "2026-02-22T23:59:00Z",
        }
        market = self.scanner._parse_market(data)
        assert market.climate_info is not None
        assert market.climate_info.market_type == "high_temp"
        assert market.climate_info.city_code == "NY"

    def test_non_climate_market_no_climate_info(self):
        data = {
            "ticker": "NBA-LAKERS-ML",
            "event_ticker": "NBA",
            "title": "Lakers vs Celtics",
            "close_time": "2026-02-22T23:59:00Z",
        }
        market = self.scanner._parse_market(data)
        assert market.climate_info is None

    def test_climate_ticker_without_parseable_info(self):
        data = {
            "ticker": "HIGHTEMP-UNKNOWN",
            "event_ticker": "HIGH",
            "title": "temperature somewhere",
            "close_time": "2026-02-22T23:59:00Z",
        }
        market = self.scanner._parse_market(data)
        assert market.category == "climate"


class TestScannerTickerDate:
    def setup_method(self):
        self.scanner = ScannerService(None)

    def test_climate_market_gets_ticker_date(self):
        data = {
            "ticker": "KXHIGHNY-26FEB22-B38.5",
            "event_ticker": "KXHIGH",
            "title": "NYC High Temperature",
            "close_time": "2026-02-22T23:59:00Z",
        }
        market = self.scanner._parse_market(data)
        assert market.ticker_date == date(2026, 2, 22)

    def test_non_climate_market_gets_ticker_date(self):
        data = {
            "ticker": "KXDOTA2GAME-26FEB16AURBB-BB",
            "event_ticker": "KXDOTA2",
            "title": "Dota 2 Game",
            "close_time": "2026-02-16T23:59:00Z",
        }
        market = self.scanner._parse_market(data)
        assert market.ticker_date == date(2026, 2, 16)
        assert market.climate_info is None

    def test_no_date_ticker(self):
        data = {
            "ticker": "NBA-LAKERS-ML",
            "event_ticker": "NBA",
            "title": "Lakers vs Celtics",
            "close_time": "2026-02-22T23:59:00Z",
        }
        market = self.scanner._parse_market(data)
        assert market.ticker_date is None


class TestScannerCategoryInference:
    def setup_method(self):
        self.scanner = ScannerService(None)

    def test_climate_from_ticker(self):
        assert self.scanner._infer_category({"ticker": "HIGHTEMP-NYC", "title": ""}) == "climate"

    def test_economics_from_ticker(self):
        assert self.scanner._infer_category({"ticker": "CPI-DEC", "title": ""}) == "economics"

    def test_climate_from_title(self):
        assert self.scanner._infer_category({"ticker": "X", "title": "NYC max temperature"}) == "climate"

    def test_economics_from_title(self):
        assert self.scanner._infer_category({"ticker": "X", "title": "Will unemployment rise?"}) == "economics"

    def test_companies_from_title(self):
        assert self.scanner._infer_category({"ticker": "X", "title": "AAPL earnings report"}) == "companies"

    def test_sports_from_ticker_nba(self):
        assert self.scanner._infer_category({"ticker": "NBA-LAKERS", "title": ""}) == "sports"

    def test_sports_from_ticker_nfl(self):
        assert self.scanner._infer_category({"ticker": "NFL-CHIEFS", "title": ""}) == "sports"

    def test_sports_from_ticker_mlb(self):
        assert self.scanner._infer_category({"ticker": "MLB-NYY", "title": ""}) == "sports"

    def test_sports_from_ticker_nhl(self):
        assert self.scanner._infer_category({"ticker": "NHL-AVS", "title": ""}) == "sports"

    def test_sports_from_ticker_ufc(self):
        assert self.scanner._infer_category({"ticker": "UFC-300", "title": ""}) == "sports"

    def test_sports_from_title_basketball(self):
        assert self.scanner._infer_category({"ticker": "X", "title": "Will the basketball game go over?"}) == "sports"

    def test_sports_from_title_super_bowl(self):
        assert self.scanner._infer_category({"ticker": "X", "title": "Who wins the super bowl?"}) == "sports"

    def test_sports_from_title_team_name(self):
        assert self.scanner._infer_category({"ticker": "X", "title": "Will the Lakers win tonight?"}) == "sports"

    def test_sports_from_title_vs(self):
        assert self.scanner._infer_category({"ticker": "X", "title": "Team A vs Team B"}) == "sports"

    def test_other_default(self):
        assert self.scanner._infer_category({"ticker": "X", "title": "something else"}) == "other"
