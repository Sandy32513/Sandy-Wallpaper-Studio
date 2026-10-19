"""DNS pinning and TLS identity tests for direct wallpaper downloads."""

from __future__ import annotations

import socket
from unittest.mock import Mock

import pytest
import requests

from app.services.download_service import (
    DownloadError,
    PublicAddressHTTPSAdapter,
    _resolve_public_address,
)


def _addrinfo(address: str) -> tuple[int, int, int, str, tuple[object, ...]]:
    if ":" in address:
        return (socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, 443, 0, 0))
    return (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, 443))


@pytest.mark.parametrize(
    "address",
    (
        "127.0.0.1",
        "10.1.2.3",
        "169.254.10.20",
        "::1",
        "fc00::1",
        "fe80::1",
        "ff02::1",
        "240.0.0.1",
    ),
)
def test_dns_resolution_rejects_non_public_addresses(
    monkeypatch: pytest.MonkeyPatch,
    address: str,
) -> None:
    resolver = Mock(return_value=[_addrinfo(address)])
    monkeypatch.setattr("app.services.download_service.socket.getaddrinfo", resolver)

    with pytest.raises(DownloadError, match="non-public"):
        _resolve_public_address("images.example", 443)

    resolver.assert_called_once_with("images.example", 443, type=socket.SOCK_STREAM)


def test_dns_resolution_rejects_mixed_public_and_private_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = Mock(return_value=[_addrinfo("93.184.216.34"), _addrinfo("192.168.1.8")])
    monkeypatch.setattr("app.services.download_service.socket.getaddrinfo", resolver)

    with pytest.raises(DownloadError, match="non-public"):
        _resolve_public_address("images.example", 443)


def test_dns_resolution_returns_a_public_ipv6_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.download_service.socket.getaddrinfo",
        Mock(return_value=[_addrinfo("2606:4700:4700::1111")]),
    )

    assert _resolve_public_address("images.example", 443) == "2606:4700:4700::1111"


def test_adapter_connects_to_pinned_ip_and_verifies_original_tls_hostname(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = Mock(return_value=[_addrinfo("93.184.216.34")])
    monkeypatch.setattr("app.services.download_service.socket.getaddrinfo", resolver)
    adapter = PublicAddressHTTPSAdapter()
    request = requests.Request("GET", "https://images.example/wallpaper.png").prepare()

    pool = adapter.get_connection_with_tls_context(request, verify=True, proxies={})
    try:
        assert pool.host == "93.184.216.34"
        assert pool.conn_kw["server_hostname"] == "images.example"
        assert pool.assert_hostname == "images.example"
        assert request.headers["Host"] == "images.example"
        adapter.cert_verify(pool, request.url, verify=True, cert=None)
        assert pool.cert_reqs == "CERT_REQUIRED"
        assert pool.ca_certs

        connected_to: list[tuple[str, int]] = []

        def fake_connect(address: tuple[str, int], *_args: object, **_kwargs: object) -> object:
            connected_to.append(address)
            return object()

        monkeypatch.setattr("urllib3.connection.connection.create_connection", fake_connect)
        connection = pool._new_conn()
        connection._new_conn()

        assert connected_to == [("93.184.216.34", 443)]
        resolver.assert_called_once_with("images.example", 443, type=socket.SOCK_STREAM)
    finally:
        pool.close()
        adapter.close()


def test_changed_dns_answer_is_resolved_again_and_private_rebinding_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = Mock(
        side_effect=[
            [_addrinfo("93.184.216.34")],
            [_addrinfo("127.0.0.1")],
        ]
    )
    monkeypatch.setattr("app.services.download_service.socket.getaddrinfo", resolver)
    adapter = PublicAddressHTTPSAdapter()
    first = requests.Request("GET", "https://images.example/a.png").prepare()
    second = requests.Request("GET", "https://images.example/b.png").prepare()

    first_pool = adapter.get_connection_with_tls_context(first, verify=True, proxies={})
    try:
        assert first_pool.host == "93.184.216.34"
        with pytest.raises(DownloadError, match="non-public"):
            adapter.get_connection_with_tls_context(second, verify=True, proxies={})
        assert resolver.call_count == 2
    finally:
        first_pool.close()
        adapter.close()


def test_adapter_fails_closed_for_invalid_urls_proxies_and_disabled_tls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = Mock(return_value=[_addrinfo("93.184.216.34")])
    monkeypatch.setattr("app.services.download_service.socket.getaddrinfo", resolver)
    adapter = PublicAddressHTTPSAdapter()

    invalid = requests.Request("GET", "https://127.0.0.1/private.png").prepare()
    with pytest.raises(DownloadError, match="public HTTPS"):
        adapter.get_connection_with_tls_context(invalid, verify=True, proxies={})

    public = requests.Request("GET", "https://images.example/a.png").prepare()
    with pytest.raises(DownloadError, match="proxies"):
        adapter.get_connection_with_tls_context(
            public,
            verify=True,
            proxies={"https": "http://proxy.example:8080"},
        )
    with pytest.raises(DownloadError, match="TLS certificate verification"):
        adapter.get_connection_with_tls_context(public, verify=False, proxies={})
    resolver.assert_not_called()
    adapter.close()
