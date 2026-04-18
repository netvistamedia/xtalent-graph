"""Publishing pipeline: CV → IPFS pin → profile root update.

The ``TalentPublisher`` is the only place in the protocol that produces side
effects: it serializes a CV, pins its bytes, and advances the mutable profile
root. All other modules are pure-function views over the resulting state.

IPFS access is abstracted behind :class:`IPFSClient`. The reference
:class:`InMemoryIPFS` is suitable for tests and demos. Production deployments
plug in a Kubo HTTP client, ``web3.storage``, or Pinata — see
``docs/architecture.md``.
"""

from __future__ import annotations

import base64
import hashlib
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from xtalent.core import ProfileRoot, XTalentCV


class PublishError(Exception):
    """Raised when a publish operation violates protocol invariants."""


@runtime_checkable
class IPFSClient(Protocol):
    """Minimal pin/fetch surface expected by the publisher."""

    def pin(self, data: bytes) -> str:
        """Persist ``data`` and return its content ID (CID)."""

    def get(self, cid: str) -> bytes:
        """Fetch previously-pinned bytes by CID. Raises ``KeyError`` if unknown."""


class InMemoryIPFS:
    """Reference :class:`IPFSClient` backed by a process-local dict.

    The CID is a deterministic sha256-based identifier prefixed with ``bafy``
    to mimic the shape of a CIDv1. It is **not** a real multihash and should
    not be trusted interchangeably with production IPFS CIDs.
    """

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def pin(self, data: bytes) -> str:
        cid = _mock_cid(data)
        self._store[cid] = data
        return cid

    def get(self, cid: str) -> bytes:
        try:
            return self._store[cid]
        except KeyError as exc:
            raise KeyError(f"cid not pinned: {cid}") from exc

    def __contains__(self, cid: str) -> bool:
        return cid in self._store


def _mock_cid(data: bytes) -> str:
    """Produce a mock CIDv1-shaped identifier. Deterministic for the same input."""
    digest = hashlib.sha256(data).digest()
    encoded = base64.b32encode(digest).decode("ascii").rstrip("=").lower()
    return f"bafy{encoded}"


class PublishRecord(BaseModel):
    """The output of a successful publish: the pinned bytes and the new root."""

    model_config = {"frozen": True}

    cid: str
    cv_markdown: str
    profile_root: ProfileRoot


class TalentPublisher:
    """Coordinates CV pinning and profile-root updates.

    The publisher is stateless apart from the injected :class:`IPFSClient` and
    an in-memory registry of profile roots keyed by handle. Swap
    ``root_store`` for a durable backend (e.g., Redis, Postgres) in production.
    """

    def __init__(
        self,
        ipfs: IPFSClient,
        root_store: dict[str, ProfileRoot] | None = None,
    ) -> None:
        self._ipfs = ipfs
        self._roots: dict[str, ProfileRoot] = root_store if root_store is not None else {}

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_root(self, handle: str) -> ProfileRoot | None:
        return self._roots.get(_canonical_handle(handle))

    def get_cv_markdown(self, cid: str) -> str:
        return self._ipfs.get(cid).decode("utf-8")

    def get_cv(self, cid: str) -> XTalentCV:
        return XTalentCV.from_markdown(self.get_cv_markdown(cid))

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def publish(self, cv: XTalentCV) -> PublishRecord:
        """Pin ``cv`` and update (or create) its profile root.

        Raises :class:`PublishError` if:

        * the handle is currently tombstoned;
        * the new CV's ``version`` is not strictly greater than the current root.
        """
        handle = _canonical_handle(cv.handle)
        current = self._roots.get(handle)

        if current is not None and current.tombstoned:
            raise PublishError(f"handle {handle} is tombstoned; re-publish refused")
        if current is not None and cv.version <= current.version:
            raise PublishError(
                f"cv version {cv.version} must be strictly greater than "
                f"current {current.version} for handle {handle}"
            )

        markdown = cv.to_markdown()
        cid = self._ipfs.pin(markdown.encode("utf-8"))
        root = cv.to_profile_root(latest_cid=cid)
        self._roots[handle] = root

        return PublishRecord(cid=cid, cv_markdown=markdown, profile_root=root)

    def tombstone(self, handle: str, reason: str | None = None) -> ProfileRoot:
        """Mark a handle as withdrawn from discovery. Idempotent."""
        key = _canonical_handle(handle)
        current = self._roots.get(key)
        if current is None:
            raise PublishError(f"unknown handle: {key}")
        updated = current.tombstone(reason=reason)
        self._roots[key] = updated
        return updated


def _canonical_handle(handle: str) -> str:
    """Normalize to the leading-``@`` form used internally."""
    return handle if handle.startswith("@") else f"@{handle}"
