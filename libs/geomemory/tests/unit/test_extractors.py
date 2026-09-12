"""Unit tests for the entity extractor module."""

from __future__ import annotations

from geomemory.knowledge.extractors import RuleBasedExtractor


class TestRuleBasedExtractor:
    def setup_method(self) -> None:
        self.ex = RuleBasedExtractor()

    def test_ndvi_detected_as_metric(self) -> None:
        hits = self.ex.extract("The NDVI index was used for vegetation assessment.")
        kinds = {name: kind for name, kind, _ in hits}
        assert "NDVI" in kinds
        assert kinds["NDVI"] == "metric"

    def test_sentinel2_detected_as_sensor(self) -> None:
        hits = self.ex.extract("Sentinel-2 imagery覆盖了区域")
        kinds = {name: kind for name, kind, _ in hits}
        assert any("Sentinel" in name for name in kinds)

    def test_salinity_detected_as_stress_type(self) -> None:
        hits = self.ex.extract("Salinity causes crop stress in Khuzestan.")
        kinds = {name: kind for name, kind, _ in hits}
        assert "Salinity" in kinds
        assert kinds["Salinity"] == "stress_type"

    def test_khuzestan_detected_as_location(self) -> None:
        hits = self.ex.extract("The study area is Khuzestan province.")
        kinds = {name: kind for name, kind, _ in hits}
        assert "Khuzestan" in kinds
        assert kinds["Khuzestan"] == "location"

    def test_unknown_text_returns_empty(self) -> None:
        hits = self.ex.extract("the quick brown fox jumps over the lazy dog")
        assert hits == []

    def test_no_duplicates(self) -> None:
        hits = self.ex.extract("NDVI and NDVI are both metrics")
        ndvi_count = sum(1 for n, k, b in hits if n == "NDVI")
        assert ndvi_count == 1

    def test_bbox_extraction(self) -> None:
        text = "The NDVI region (51 • 32 • 52 • 33) was analyzed."
        hits = self.ex.extract(text)
        bboxes = [b for _, _, b in hits if b is not None]
        assert len(bboxes) >= 1
        assert bboxes[0] == (32.0, 33.0, 51.0, 52.0)

    def test_empty_string(self) -> None:
        assert self.ex.extract("") == []
