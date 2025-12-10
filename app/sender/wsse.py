"""WS-Security helpers for Mossos integration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from lxml.etree import QName
from zeep import ns
from zeep.wsse.signature import BinarySignature
from zeep.wsse.utils import WSU, get_security_header


class TimestampedBinarySignature(BinarySignature):
    """BinarySignature variant that injects and signs a WS-Security Timestamp.

    Mossos requiere que el Timestamp esté dentro de ``wsse:Security`` y que se
    firme junto al Body. Este wrapper se asegura de crear el Timestamp con un
    ``wsu:Id`` único y lo deja listo para que la firma de Zeep lo incluya en las
    referencias firmadas.
    """

    def __init__(self, *args, timestamp_ttl_seconds: int = 300, **kwargs):
        self.timestamp_ttl_seconds = timestamp_ttl_seconds
        super().__init__(*args, **kwargs)

    def _create_timestamp(self):
        created = datetime.now(timezone.utc).replace(microsecond=0)
        expires = created + timedelta(seconds=self.timestamp_ttl_seconds)
        timestamp = WSU.Timestamp(WSU.Created(created.isoformat()), WSU.Expires(expires.isoformat()))
        timestamp.set(QName(ns.WSU, "Id"), f"TS-{uuid4()}")
        return timestamp

    def apply(self, envelope, headers):
        security = get_security_header(envelope)
        timestamp = security.find(QName(ns.WSU, "Timestamp"))
        if timestamp is None:
            security.insert(0, self._create_timestamp())
        return super().apply(envelope, headers)


__all__ = ["TimestampedBinarySignature"]
