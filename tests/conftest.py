"""All automated tests are offline; even accidental DNS/network attempts fail."""
import socket
import pytest


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('Tests must not open sockets or perform DNS resolution')
    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket.socket, 'connect_ex', blocked)
    monkeypatch.setattr(socket, 'create_connection', blocked)
    monkeypatch.setattr(socket, 'getaddrinfo', blocked)
