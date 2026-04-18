"""Kubo IPFS implementation of :class:`xtalent.publish.IPFSClient`.

Real pinning, real CIDs. Talks to a Kubo node's HTTP API (the default
endpoint for ``ipfs daemon`` is ``http://localhost:5001``).

Usage
-----

Zero-config (local daemon)::

    from xtalent.backends.kubo import KuboIPFS
    ipfs = KuboIPFS()                                   # http://localhost:5001

Remote / authenticated::

    ipfs = KuboIPFS(url="https://ipfs.my-co.internal:5001", auth=("user", "pass"))

Use with the publisher::

    from xtalent import TalentPublisher
    publisher = TalentPublisher(ipfs=KuboIPFS())

Or let the reference server pick it up::

    XTALENT_IPFS_MODE=kubo XTALENT_KUBO_URL=http://localhost:5001 \\
        uvicorn xtalent.api:app --reload

Naming note
-----------
The :class:`~xtalent.publish.IPFSClient` protocol uses ``pin(data) -> cid``
as "persist these bytes and return their CID". That semantics predates this
adapter and is preserved. IPFS itself has a separate "pin this CID"
operation, which this class exposes as :meth:`pin_cid` to avoid the name
collision. :meth:`add_bytes` / :meth:`get_bytes` are supplied as
IPFS-idiomatic aliases for :meth:`pin` / :meth:`get`.
"""

from __future__ import annotations

from typing import Any

import httpx

__all__ = [
    "DEFAULT_KUBO_URL",
    "KuboConnectionError",
    "KuboError",
    "KuboIPFS",
]

DEFAULT_KUBO_URL = "http://localhost:5001"


class KuboError(RuntimeError):
    """Base class for Kubo HTTP API failures."""


class KuboConnectionError(KuboError):
    """Raised when the Kubo node is unreachable (connect/read timeout or refused)."""


class KuboIPFS:
    """Pin and fetch bytes via a Kubo node's HTTP API.

    The class implements the :class:`~xtalent.publish.IPFSClient` protocol
    (``pin(data) -> cid`` and ``get(cid) -> bytes``) so it is a drop-in
    replacement for :class:`~xtalent.publish.InMemoryIPFS`.
    """

    def __init__(
        self,
        *,
        url: str = DEFAULT_KUBO_URL,
        auth: tuple[str, str] | None = None,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        """Construct a client.

        Args:
            url: Base URL of the Kubo HTTP API (e.g. ``http://localhost:5001``).
            auth: Optional ``(username, password)`` pair for HTTP basic auth.
            timeout: Per-request timeout in seconds.
            client: Inject a pre-configured :class:`httpx.Client`. Mostly useful
                for tests (via :class:`httpx.MockTransport`) — when set, ``url``,
                ``auth``, and ``timeout`` are ignored.
        """
        self._base_url = url.rstrip("/")
        self._owns_client = client is None
        if client is None:
            self._client = httpx.Client(
                base_url=self._base_url,
                auth=auth,
                timeout=timeout,
            )
        else:
            self._client = client

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> KuboIPFS:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # IPFSClient protocol
    # ------------------------------------------------------------------

    def pin(self, data: bytes) -> str:
        """Add ``data`` to the Kubo node and return its CID.

        Kubo's ``/api/v0/add`` pins the content by default, so the name
        mirrors the protocol: the bytes are persisted *and* pinned.
        """
        return self.add_bytes(data)

    def get(self, cid: str) -> bytes:
        """Fetch content by CID. Mirrors ``InMemoryIPFS.get``."""
        return self.get_bytes(cid)

    # ------------------------------------------------------------------
    # IPFS-idiomatic surface
    # ------------------------------------------------------------------

    def add_bytes(self, data: bytes, filename: str | None = None) -> str:
        """Add ``data`` to IPFS and return the resulting CID.

        ``filename`` is passed to Kubo for multipart metadata; it does not
        affect the CID when the upload is a single file without
        ``wrap-with-directory``.
        """
        files = {"file": (filename or "data", data, "application/octet-stream")}
        payload = self._post_json("/api/v0/add", files=files)
        cid = payload.get("Hash")
        if not isinstance(cid, str) or not cid:
            raise KuboError(f"unexpected /api/v0/add response: {payload!r}")
        return cid

    def get_bytes(self, cid: str) -> bytes:
        """Fetch content by CID. Raises :class:`KuboError` if the node lacks it."""
        try:
            response = self._client.post("/api/v0/cat", params={"arg": cid})
        except httpx.ConnectError as exc:
            raise KuboConnectionError(self._unreachable_message()) from exc
        except httpx.TimeoutException as exc:
            raise KuboConnectionError(f"timeout fetching cid={cid}") from exc
        if response.status_code != 200:
            raise KuboError(_describe_error(response, f"cat cid={cid}"))
        return response.content

    def pin_cid(self, cid: str) -> None:
        """Explicitly pin an existing CID.

        Use this when the CID was added by a third party and you want to
        ensure your node keeps the content. Content added via
        :meth:`add_bytes` / :meth:`pin` is already pinned.
        """
        self._post_json("/api/v0/pin/add", params={"arg": cid})

    def version(self) -> dict[str, Any]:
        """Return Kubo's ``/api/v0/version`` payload. Useful as a health check."""
        return self._post_json("/api/v0/version")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _post_json(
        self,
        path: str,
        *,
        files: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self._client.post(path, files=files, params=params)
        except httpx.ConnectError as exc:
            raise KuboConnectionError(self._unreachable_message()) from exc
        except httpx.TimeoutException as exc:
            raise KuboConnectionError(f"timeout on {path}") from exc

        if response.status_code != 200:
            raise KuboError(_describe_error(response, path))

        try:
            payload = response.json()
        except ValueError as exc:
            raise KuboError(
                f"expected JSON from {path}, got content-type="
                f"{response.headers.get('content-type')!r}"
            ) from exc

        if not isinstance(payload, dict):
            raise KuboError(f"expected a JSON object from {path}, got {type(payload).__name__}")
        return payload

    def _unreachable_message(self) -> str:
        return (
            f"Kubo node unreachable at {self._base_url}. Start a local node with "
            f"`ipfs daemon` or bring the dev stack up via "
            f"`docker compose -f docker-compose.dev.yml up`."
        )


def _describe_error(response: httpx.Response, context: str) -> str:
    """Build a human-legible error message from a Kubo error response."""
    try:
        body = response.json()
        if isinstance(body, dict) and "Message" in body:
            return f"kubo {context} failed: {body.get('Message')} (code={body.get('Code')})"
    except ValueError:
        pass
    truncated = response.text[:200]
    return f"kubo {context} failed: HTTP {response.status_code} {truncated!r}"
