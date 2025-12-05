from __future__ import annotations

import base64
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from lxml import etree

from app.sender.mossos_client import MossosZeepClient


def _write_dummy_wsdl(target: Path) -> Path:
    wsdl_content = """
    <definitions xmlns="http://schemas.xmlsoap.org/wsdl/" xmlns:tns="http://dgp.gencat.cat/matricules"
        xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/" xmlns:xs="http://www.w3.org/2001/XMLSchema"
        targetNamespace="http://dgp.gencat.cat/matricules">
        <types>
            <xs:schema targetNamespace="http://dgp.gencat.cat/matricules" elementFormDefault="qualified">
                <xs:complexType name="MatriculaType">
                    <xs:sequence>
                        <xs:element name="codiLector" type="xs:string" />
                        <xs:element name="matricula" type="xs:string" />
                        <xs:element name="dataLectura" type="xs:string" />
                        <xs:element name="horaLectura" type="xs:string" />
                        <xs:element name="imgMatricula" type="xs:base64Binary" />
                        <xs:element name="imgContext" type="xs:base64Binary" minOccurs="0" />
                        <xs:element name="coordenadaX" type="xs:string" minOccurs="0" />
                        <xs:element name="coordenadaY" type="xs:string" minOccurs="0" />
                        <xs:element name="marca" type="xs:string" minOccurs="0" />
                        <xs:element name="model" type="xs:string" minOccurs="0" />
                        <xs:element name="color" type="xs:string" minOccurs="0" />
                        <xs:element name="tipusVehicle" type="xs:string" minOccurs="0" />
                        <xs:element name="pais" type="xs:string" minOccurs="0" />
                    </xs:sequence>
                </xs:complexType>
                <xs:complexType name="MatriculaResponseType">
                    <xs:sequence>
                        <xs:element name="codiRetorn" type="xs:string" minOccurs="0" />
                    </xs:sequence>
                </xs:complexType>
                <xs:element name="matriculaRequest" type="tns:MatriculaType" />
                <xs:element name="matriculaResponse" type="tns:MatriculaResponseType" />
            </xs:schema>
        </types>
        <message name="matriculaRequest">
            <part name="matriculaRequest" element="tns:matriculaRequest" />
        </message>
        <message name="matriculaResponse">
            <part name="matriculaResponse" element="tns:matriculaResponse" />
        </message>
        <portType name="MatriculesSoap11">
            <operation name="matricula">
                <input message="tns:matriculaRequest" />
                <output message="tns:matriculaResponse" />
            </operation>
        </portType>
        <binding name="MatriculesSoap11" type="tns:MatriculesSoap11">
            <soap:binding transport="http://schemas.xmlsoap.org/soap/http" style="document" />
            <operation name="matricula">
                <soap:operation soapAction="matricula" style="document" />
                <input><soap:body use="literal" /></input>
                <output><soap:body use="literal" /></output>
            </operation>
        </binding>
        <service name="MatriculesService">
            <port name="MatriculesSoap11" binding="tns:MatriculesSoap11">
                <soap:address location="http://example.com/matricules" />
            </port>
        </service>
    </definitions>
    """
    wsdl_file = target / "matricules.wsdl"
    wsdl_file.write_text(wsdl_content.strip())
    return wsdl_file


def _generate_certificates(tmp_path: Path) -> tuple[str, str]:
    key_path = tmp_path / "key.pem"
    cert_path = tmp_path / "cert.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-days",
            "1",
            "-nodes",
            "-subj",
            "/CN=test",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return str(cert_path), str(key_path)


def test_build_matricula_request_includes_images(tmp_path):
    wsdl_path = _write_dummy_wsdl(tmp_path)
    cert_path, key_path = _generate_certificates(tmp_path)

    ocr_image = tmp_path / "ocr.jpg"
    ctx_image = tmp_path / "ctx.jpg"
    ocr_image.write_bytes(b"ocr-bytes")
    ctx_image.write_bytes(b"ctx-bytes")

    class DummyReading:
        def __init__(self):
            self.id = 1
            self.plate = "1234ABC"
            self.timestamp_utc = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            self.image_ocr_path = str(ocr_image)
            self.has_image_ctx = True
            self.image_ctx_path = str(ctx_image)
            self.country_code = "ES"
            self.brand = None
            self.model = None
            self.color = None
            self.vehicle_type = None

    class DummyCamera:
        def __init__(self):
            self.codigo_lector = "CAM01"
            self.coord_x = "1.23"
            self.coord_y = "4.56"
            self.utm_x = None
            self.utm_y = None
            self.serial_number = "SN1"

    client = MossosZeepClient(
        wsdl_url=str(wsdl_path),
        endpoint_url="http://override.local/matricules",
        cert_path=cert_path,
        key_path=key_path,
        timeout=2.0,
    )

    reading = DummyReading()
    camera = DummyCamera()
    request_el = client.build_matricula_request(reading, camera)

    assert hasattr(request_el, "codiLector")
    assert request_el.codiLector == "CAM01"
    assert request_el.dataLectura == "2024-01-01"
    assert base64.b64decode(request_el.imgMatricula) == b"ocr-bytes"
    assert base64.b64decode(request_el.imgContext) == b"ctx-bytes"

    message = client.client.create_message(
        client.service, "matricula", matriculaRequest=request_el
    )
    xml_bytes = etree.tostring(message)
    assert b"Security" in xml_bytes
