import socket

from app.ingest import service


def test_read_connection_payload_returns_data_on_inactivity_timeout(monkeypatch):
    monkeypatch.setattr(service, "READ_TIMEOUT_SECONDS", 0.05)

    server_sock, client_sock = socket.socketpair()
    try:
        client_sock.sendall(b"<MESSAGE><PLATE_STRING>1234ABC</PLATE_STRING></MESSAGE>")
        payload = service._read_connection_payload(server_sock, ("127.0.0.1", 12345))
    finally:
        client_sock.close()

    assert payload.startswith("<MESSAGE>")
    assert payload.endswith("</MESSAGE>")


def test_read_connection_payload_empty_when_no_data(monkeypatch):
    monkeypatch.setattr(service, "READ_TIMEOUT_SECONDS", 0.05)

    server_sock, client_sock = socket.socketpair()
    try:
        payload = service._read_connection_payload(server_sock, ("127.0.0.1", 12345))
    finally:
        client_sock.close()

    assert payload == ""
