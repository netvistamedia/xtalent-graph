"""Tests for xtalent.backends.kubo.

These tests use :class:`httpx.MockTransport` to simulate a Kubo node,
keeping the suite deterministic and offline. A trailing ``@pytest.mark
.skipif`` integration test against a real local daemon is included for
completeness — it is skipped when no daemon is listening.
"""

from __future__ import annotations

import json
import socket
from collections.abc import Callable

import httpx
import pytest

from xtalent import PublishRecord, TalentPublisher, XTalentCV, build_ipfs_client
from xtalent.backends.kubo import (
    DEFAULT_KUBO_URL,
    KuboConnectionError,
    KuboError,
    KuboIPFS,
)

_REAL_CID = "QmT78zSuBmuS4z925WZfrqQ1qHaJ56DQaTfyMUF7F8ff5o"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(handler: Callable[[httpx.Request], httpx.Response]) -> KuboIPFS:
    """Build a KuboIPFS backed by a MockTransport — no network, fully deterministic."""
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(base_url=DEFAULT_KUBO_URL, transport=transport)
    return KuboIPFS(client=http_client)


def _add_handler(expected_body_contains: bytes | None = None) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v0/add":
            if expected_body_contains is not None:
                assert expected_body_contains in request.content
            return httpx.Response(
                200,
                json={"Name": "data", "Hash": _REAL_CID, "Size": "42"},
            )
        if request.url.path == "/api/v0/cat":
            return httpx.Response(200, content=b"hello world")
        if request.url.path == "/api/v0/version":
            return httpx.Response(200, json={"Version": "0.29.0"})
        return httpx.Response(404)

    return handler


# ---------------------------------------------------------------------------
# Unit tests (MockTransport)
# ---------------------------------------------------------------------------


def test_add_bytes_returns_cid() -> None:
    client = _make_client(_add_handler(expected_body_contains=b"hello"))
    cid = client.add_bytes(b"hello", filename="greeting.txt")
    assert cid == _REAL_CID


def test_pin_is_alias_of_add_bytes() -> None:
    """Protocol-compliant: pin(data) -> cid, same bytes yield same response."""
    client = _make_client(_add_handler())
    cid = client.pin(b"anything")
    assert cid == _REAL_CID


def test_get_bytes_roundtrip() -> None:
    client = _make_client(_add_handler())
    assert client.get_bytes(_REAL_CID) == b"hello world"
    assert client.get(_REAL_CID) == b"hello world"  # protocol alias


def test_pin_cid_issues_pin_add() -> None:
    seen: dict[str, str | None] = {"path": None, "arg": None}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["arg"] = request.url.params.get("arg")
        return httpx.Response(200, json={"Pins": [_REAL_CID]})

    client = _make_client(handler)
    client.pin_cid(_REAL_CID)
    assert seen["path"] == "/api/v0/pin/add"
    assert seen["arg"] == _REAL_CID


def test_version_health_check() -> None:
    client = _make_client(_add_handler())
    assert client.version() == {"Version": "0.29.0"}


def test_connect_error_is_wrapped() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = _make_client(handler)
    with pytest.raises(KuboConnectionError, match="unreachable"):
        client.get_bytes(_REAL_CID)


def test_timeout_is_wrapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = _make_client(handler)
    with pytest.raises(KuboConnectionError, match="timeout"):
        client.add_bytes(b"x")


def test_kubo_error_message_parsed() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            json={"Message": "invalid path", "Code": 0, "Type": "error"},
        )

    client = _make_client(handler)
    with pytest.raises(KuboError, match="invalid path"):
        client.get_bytes("Qmbad")


def test_missing_hash_in_add_response_raises() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"Name": "data"})

    client = _make_client(handler)
    with pytest.raises(KuboError, match="unexpected"):
        client.add_bytes(b"x")


def test_build_ipfs_client_dispatches_to_kubo() -> None:
    transport = httpx.MockTransport(_add_handler())
    http_client = httpx.Client(base_url=DEFAULT_KUBO_URL, transport=transport)
    ipfs = build_ipfs_client("kubo", client=http_client)
    assert isinstance(ipfs, KuboIPFS)
    assert ipfs.add_bytes(b"hello") == _REAL_CID


def test_build_ipfs_client_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="unknown IPFS mode"):
        build_ipfs_client("s3")


def test_build_ipfs_client_memory_rejects_options() -> None:
    with pytest.raises(ValueError, match="takes no options"):
        build_ipfs_client("memory", url="http://x")


# ---------------------------------------------------------------------------
# Publisher integration
# ---------------------------------------------------------------------------


def test_publisher_uses_kubo_pinning(sample_cv: XTalentCV) -> None:
    client = _make_client(_add_handler())
    publisher = TalentPublisher(ipfs=client)
    record = publisher.publish(sample_cv)
    assert isinstance(record, PublishRecord)
    assert record.cid == _REAL_CID


# ---------------------------------------------------------------------------
# Optional: real integration test (skipped when no daemon is listening)
# ---------------------------------------------------------------------------


def _local_kubo_reachable(host: str = "127.0.0.1", port: int = 5001) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


@pytest.mark.skipif(
    not _local_kubo_reachable(),
    reason="no local Kubo daemon on :5001",
)
def test_integration_roundtrip_against_real_kubo() -> None:
    with KuboIPFS() as ipfs:
        cid = ipfs.add_bytes(b'{"hello":"world"}', filename="hello.json")
        assert cid
        fetched = ipfs.get_bytes(cid)
        assert json.loads(fetched) == {"hello": "world"}
