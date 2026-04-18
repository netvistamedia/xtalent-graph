"""Ed25519 signing for :class:`~xtalent.core.ProfileRoot`.

What signatures attest to
-------------------------
A signature proves **self-consistency**: "this pubkey signed this root
content." It does **not** answer the adjacent question — "is this pubkey
really @ada's?". Binding pubkey → handle is an *out-of-band* problem
(e.g. DNS TXT records, a central trust registry, or a Keybase-style proof
chain). v0.1 ships the signing primitive; trust-root discovery is a later
RFC.

Binding the pubkey into the signed payload
------------------------------------------
We sign the canonical JSON form of the root **with ``pubkey`` included**
and **``signature`` excluded**. That means an attacker who swaps in their
own pubkey will invalidate the signature — the signature commits to the
pubkey used for verification.

Canonicalization
----------------
:func:`canonical_bytes` produces the exact bytes that are signed, so
implementations in other languages can reproduce the digest:

1. Serialize the root via Pydantic ``model_dump(mode="json", by_alias=True)``.
2. Drop the ``signature`` field (if present).
3. ``json.dumps(..., sort_keys=True, separators=(",", ":"),
   ensure_ascii=False)``.
4. UTF-8 encode.

Key format
----------
Public and private keys are carried as strings of the form
``ed25519:<base64(raw-32-bytes)>``. The algorithm prefix reserves room
for future key types (e.g. ``secp256k1:``) without another schema bump.

Out of scope for v0.1
---------------------
- Key rotation and revocation.
- Signing full CVs (only profile roots).
- Hardware-backed keys (HSM, cloud KMS). Applications that want those
  can still call :func:`canonical_bytes` and hand the bytes to their
  signer of choice.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from xtalent.core import ProfileRoot

ED25519_PREFIX = "ed25519:"
_ED25519_PUBLIC_KEY_LEN = 32
_ED25519_SIGNATURE_LEN = 64


class SignatureError(Exception):
    """Raised when a signature is missing, malformed, or does not verify."""


@dataclass(frozen=True)
class KeyPair:
    """Convenience pair of base64-encoded ed25519 keys.

    Both fields carry the ``ed25519:`` prefix. Treat ``private_key`` as a
    secret: it is the full 32-byte seed, base64-encoded.
    """

    public_key: str
    private_key: str


# ---------------------------------------------------------------------------
# Key handling
# ---------------------------------------------------------------------------


def generate_keypair() -> KeyPair:
    """Produce a fresh Ed25519 keypair in protocol string form."""
    private = Ed25519PrivateKey.generate()
    public = private.public_key()

    private_bytes = private.private_bytes_raw()
    public_bytes = public.public_bytes_raw()

    return KeyPair(
        public_key=_encode_key(public_bytes),
        private_key=_encode_key(private_bytes),
    )


def _encode_key(raw: bytes) -> str:
    return f"{ED25519_PREFIX}{base64.b64encode(raw).decode('ascii')}"


def _decode_key(encoded: str, *, expected_len: int, kind: str) -> bytes:
    if not encoded.startswith(ED25519_PREFIX):
        raise SignatureError(f"{kind} must start with {ED25519_PREFIX!r}: {encoded!r}")
    try:
        raw = base64.b64decode(encoded[len(ED25519_PREFIX):], validate=True)
    except (ValueError, binascii.Error) as exc:
        raise SignatureError(f"{kind} has invalid base64 payload") from exc
    if len(raw) != expected_len:
        raise SignatureError(
            f"{kind} must decode to {expected_len} bytes, got {len(raw)}"
        )
    return raw


def _load_private(private_key: str) -> Ed25519PrivateKey:
    raw = _decode_key(private_key, expected_len=_ED25519_PUBLIC_KEY_LEN, kind="private key")
    return Ed25519PrivateKey.from_private_bytes(raw)


def _load_public(public_key: str) -> Ed25519PublicKey:
    raw = _decode_key(public_key, expected_len=_ED25519_PUBLIC_KEY_LEN, kind="public key")
    return Ed25519PublicKey.from_public_bytes(raw)


# ---------------------------------------------------------------------------
# Canonical form
# ---------------------------------------------------------------------------


def canonical_bytes(root: ProfileRoot) -> bytes:
    """Return the exact bytes that are signed.

    The output is deterministic: serializing the same root twice yields
    byte-identical output, and two implementations of the protocol (Python,
    TypeScript, …) must agree on this sequence.
    """
    payload = root.model_dump(mode="json", by_alias=True, exclude={"signature"})
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# Sign and verify
# ---------------------------------------------------------------------------


def sign_profile_root(root: ProfileRoot, private_key: str) -> ProfileRoot:
    """Return a copy of ``root`` with ``pubkey`` and ``signature`` set.

    The passed ``root`` is not mutated. If ``root.pubkey`` was already set,
    it must match the public half of ``private_key`` — this catches silent
    mismatches between the claimed and actual key.
    """
    priv = _load_private(private_key)
    pub_bytes = priv.public_key().public_bytes_raw()
    pubkey = _encode_key(pub_bytes)

    if root.pubkey is not None and root.pubkey != pubkey:
        raise SignatureError(
            "root.pubkey does not match the public half of the private key"
        )

    with_pubkey = root.model_copy(update={"pubkey": pubkey, "signature": None})
    message = canonical_bytes(with_pubkey)
    signature_bytes = priv.sign(message)
    return with_pubkey.model_copy(update={"signature": _encode_key(signature_bytes)})


def verify_profile_root(root: ProfileRoot) -> None:
    """Raise :class:`SignatureError` if ``root`` is unsigned or invalid.

    On success, returns ``None``. Callers that want a boolean helper can
    wrap this with ``try / except SignatureError``.
    """
    if root.pubkey is None or root.signature is None:
        raise SignatureError("profile root is unsigned")

    try:
        pub = _load_public(root.pubkey)
    except SignatureError:
        raise

    signature_raw = _decode_key(
        root.signature,
        expected_len=_ED25519_SIGNATURE_LEN,
        kind="signature",
    )
    message = canonical_bytes(root)

    try:
        pub.verify(signature_raw, message)
    except InvalidSignature as exc:
        raise SignatureError("signature does not verify") from exc


def is_signed(root: ProfileRoot) -> bool:
    """Return True iff both ``pubkey`` and ``signature`` are present."""
    return root.pubkey is not None and root.signature is not None


__all__ = [
    "ED25519_PREFIX",
    "KeyPair",
    "SignatureError",
    "canonical_bytes",
    "generate_keypair",
    "is_signed",
    "sign_profile_root",
    "verify_profile_root",
]
