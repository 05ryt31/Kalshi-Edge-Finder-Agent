import pytest

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

    def test_other_default(self):
        assert self.scanner._infer_category({"ticker": "X", "title": "something else"}) == "other"
