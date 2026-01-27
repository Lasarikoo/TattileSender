import pytest
from fastapi import HTTPException

from app.api.lectorvision import ingest_lectorvision
from app.ingest.lectorvision import build_tattile_xml_from_lectorvision, parse_lectorvision_timestamp
from app.ingest.parser import parse_tattile_xml


def test_parse_lectorvision_timestamp():
    date_str, time_str = parse_lectorvision_timestamp("2026/01/23 09:25:57.000")

    assert date_str == "2026-01-23"
    assert time_str == "09-25-57-000"


def test_build_tattile_xml_from_lectorvision():
    payload = {
        "Plate": "1234ABC",
        "TimeStamp": "2026/01/23 09:25:57.000",
        "SerialNumber": "LV-01",
        "Fiability": 87,
        "Direction": "IN",
        "LaneNumber": 2,
        "LaneName": "Carril 2",
        "PlateCoord": [10, 20, 110, 220],
        "Country": 724,
    }

    xml_str, meta = build_tattile_xml_from_lectorvision(payload)

    assert meta["plate"] == "1234ABC"
    assert meta["device_sn"] == "LV-01"

    parsed = parse_tattile_xml(xml_str)
    assert parsed["plate"] == "1234ABC"
    assert parsed["device_sn"] == "LV-01"
    assert parsed["ocr_score"] == 87
    assert parsed["direction"] == "IN"
    assert parsed["lane_id"] == 2
    assert parsed["lane_descr"] == "Carril 2"
    assert parsed["bbox_min_x"] == 10
    assert parsed["bbox_min_y"] == 20
    assert parsed["bbox_max_x"] == 110
    assert parsed["bbox_max_y"] == 220
    assert parsed["country_code"] == "724"
    assert parsed["country"] == "ES"


def test_lectorvision_endpoint_rejects_missing_fields():
    with pytest.raises(HTTPException) as excinfo:
        ingest_lectorvision({"TimeStamp": "2026/01/23 09:25:57.000"})

    assert excinfo.value.status_code == 400
    assert "Plate" in excinfo.value.detail


def test_lectorvision_endpoint_accepts_payload(monkeypatch):
    captured = {}

    def fake_process(xml_str, session):
        captured["xml"] = xml_str

    class DummyQuery:
        def __init__(self, result):
            self._result = result

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return self._result

    class DummySession:
        def __init__(self, result):
            self._result = result

        def query(self, model):
            return DummyQuery(self._result)

        def rollback(self) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.api.lectorvision.process_tattile_payload", fake_process)
    monkeypatch.setattr("app.api.lectorvision.SessionLocal", lambda: DummySession(object()))

    payload = {
        "Plate": "9999ZZZ",
        "TimeStamp": "2026/01/23 09:25:57.000",
        "SerialNumber": "LV-02",
    }
    response = ingest_lectorvision(payload)

    assert response["status"] == "accepted"
    assert response["plate"] == "9999ZZZ"
    assert "PLATE_STRING" in captured["xml"]


def test_lectorvision_endpoint_rejects_unregistered_camera(monkeypatch):
    class DummyQuery:
        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return None

    class DummySession:
        def query(self, model):
            return DummyQuery()

        def rollback(self) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr("app.api.lectorvision.SessionLocal", lambda: DummySession())

    payload = {
        "Plate": "8888YYY",
        "TimeStamp": "2026/01/23 09:25:57.000",
        "SerialNumber": "LV-404",
    }

    with pytest.raises(HTTPException) as excinfo:
        ingest_lectorvision(payload)

    assert excinfo.value.status_code == 404
