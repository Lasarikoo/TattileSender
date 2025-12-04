from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ingest.service import process_tattile_payload
from app.models import Base, Camera, MessageQueue, Municipality


def test_process_tattile_payload_creates_records():
    engine = create_engine("sqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    Base.metadata.create_all(engine)

    session = TestingSession()
    municipality = Municipality(name="Test Town", active=True)
    session.add(municipality)
    session.flush()

    camera = Camera(serial_number="DEV-001", codigo_lector="C1", municipality_id=municipality.id)
    session.add(camera)
    session.commit()

    xml_input = """
    <MESSAGE>
        <PLATE_STRING>5555AAA</PLATE_STRING>
        <DATE>2024-05-01</DATE>
        <TIME>08-10-11-500</TIME>
        <DEVICE_SN>DEV-001</DEVICE_SN>
        <OCRSCORE>080</OCRSCORE>
    </MESSAGE>
    """

    process_tattile_payload(xml_input, session)

    readings_count = session.query(Camera).first().readings
    assert len(readings_count) == 1

    message = session.query(MessageQueue).first()
    assert message is not None
    assert message.status == "PENDING"
    assert message.reading_id == readings_count[0].id

    # Confirma persistencia y fecha creada
    assert readings_count[0].plate == "5555AAA"
    assert isinstance(readings_count[0].created_at, datetime)
