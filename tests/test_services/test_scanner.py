from src.services.scanner import ScannerService


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
