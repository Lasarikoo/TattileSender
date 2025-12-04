from datetime import datetime, timezone

import pytest

from app.ingest.parser import TattileParseError, parse_tattile_xml


def test_parse_tattile_xml_success():
    xml_input = """
    <MESSAGE>
        <PLATE_STRING>1234ABC</PLATE_STRING>
        <DATE>2024-04-30</DATE>
        <TIME>12-34-56-789</TIME>
        <DEVICE_SN>TAT-XYZ-01</DEVICE_SN>
        <OCRSCORE>093</OCRSCORE>
        <DIRECTION>GOAWAY</DIRECTION>
        <LANE_ID>2</LANE_ID>
        <LANE_DESCR>Carril central</LANE_DESCR>
        <ORIG_PLATE_MIN_X>10</ORIG_PLATE_MIN_X>
        <ORIG_PLATE_MIN_Y>20</ORIG_PLATE_MIN_Y>
        <ORIG_PLATE_MAX_X>110</ORIG_PLATE_MAX_X>
        <ORIG_PLATE_MAX_Y>220</ORIG_PLATE_MAX_Y>
        <CHAR_HEIGHT>30</CHAR_HEIGHT>
        <PLATE_COUNTRY_CODE>ESP</PLATE_COUNTRY_CODE>
        <PLATE_COUNTRY>Spain</PLATE_COUNTRY>
        <IMAGE_OCR>BASE64OCR</IMAGE_OCR>
        <IMAGE_CTX></IMAGE_CTX>
    </MESSAGE>
    """

    result = parse_tattile_xml(xml_input)

    assert result["plate"] == "1234ABC"
    assert result["device_sn"] == "TAT-XYZ-01"
    assert result["ocr_score"] == 93
    assert result["has_image_ocr"] is True
    assert result["has_image_ctx"] is False
    assert result["raw_xml"].strip().startswith("<MESSAGE>")

    expected_timestamp = datetime(2024, 4, 30, 12, 34, 56, 789000, tzinfo=timezone.utc)
    assert result["timestamp_utc"] == expected_timestamp

    assert result["bbox_min_x"] == 10
    assert result["bbox_min_y"] == 20
    assert result["bbox_max_x"] == 110
    assert result["bbox_max_y"] == 220
    assert result["char_height"] == 30


@pytest.mark.parametrize("missing_tag", ["PLATE_STRING", "DEVICE_SN"])
def test_parse_tattile_xml_missing_required(missing_tag):
    xml_input = f"""
    <MESSAGE>
        <PLATE_STRING>1234ABC</PLATE_STRING>
        <DEVICE_SN>SN-1</DEVICE_SN>
    </MESSAGE>
    """

    xml_input = xml_input.replace(f"<{missing_tag}>", f"<{missing_tag}-X>")
    with pytest.raises(TattileParseError):
        parse_tattile_xml(xml_input)
