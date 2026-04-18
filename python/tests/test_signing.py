"""Tests for xtalent.signing — ed25519 signing of profile roots."""

from __future__ import annotations

import base64
import json

import pytest

from xtalent import (
    PublishRecord,
    SignatureError,
    TalentPublisher,
    TalentSearchIndex,
    XTalentCV,
    canonical_bytes,
    generate_keypair,
    is_signed,
    sign_profile_root,
    verify_profile_root,
)
from xtalent.signing import ED25519_PREFIX

# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------


def test_generate_keypair_has_expected_shape() -> None:
    kp = generate_keypair()
    assert kp.public_key.startswith(ED25519_PREFIX)
    assert kp.private_key.startswith(ED25519_PREFIX)
    for encoded in (kp.public_key, kp.private_key):
        raw = base64.b64decode(encoded[len(ED25519_PREFIX):])
        assert len(raw) == 32


def test_two_keypairs_are_independent() -> None:
    a, b = generate_keypair(), generate_keypair()
    assert a.public_key != b.public_key
    assert a.private_key != b.private_key


# ---------------------------------------------------------------------------
# Canonical form
# ---------------------------------------------------------------------------


def test_canonical_bytes_is_stable(publisher: TalentPublisher, sample_cv: XTalentCV) -> None:
    record = publisher.publish(sample_cv)
    first = canonical_bytes(record.profile_root)
    second = canonical_bytes(record.profile_root)
    assert first == second


def test_canonical_bytes_excludes_signature(
    publisher: TalentPublisher, sample_cv: XTalentCV
) -> None:
    record = publisher.publish(sample_cv)
    kp = generate_keypair()
    signed = sign_profile_root(record.profile_root, kp.private_key)
    payload = json.loads(canonical_bytes(signed))
    assert "signature" not in payload
    # pubkey is included in the signed content (so attackers can't swap it).
    assert payload["pubkey"] == kp.public_key


# ---------------------------------------------------------------------------
# Sign / verify roundtrip
# ---------------------------------------------------------------------------


def test_sign_then_verify_roundtrip(
    publisher: TalentPublisher, sample_cv: XTalentCV
) -> None:
    record = publisher.publish(sample_cv)
    kp = generate_keypair()
    signed = sign_profile_root(record.profile_root, kp.private_key)

    assert signed.pubkey == kp.public_key
    assert signed.signature is not None
    assert signed.signature.startswith(ED25519_PREFIX)
    assert is_signed(signed)

    verify_profile_root(signed)  # raises on failure


def test_signing_does_not_mutate_input(
    publisher: TalentPublisher, sample_cv: XTalentCV
) -> None:
    record = publisher.publish(sample_cv)
    before = record.profile_root.model_copy()
    kp = generate_keypair()
    sign_profile_root(record.profile_root, kp.private_key)
    assert record.profile_root == before


def test_verify_unsigned_root_raises(
    publisher: TalentPublisher, sample_cv: XTalentCV
) -> None:
    record = publisher.publish(sample_cv)
    with pytest.raises(SignatureError, match="unsigned"):
        verify_profile_root(record.profile_root)


# ---------------------------------------------------------------------------
# Tamper resistance
# ---------------------------------------------------------------------------


def test_tampered_root_fails_verification(
    publisher: TalentPublisher, sample_cv: XTalentCV
) -> None:
    record = publisher.publish(sample_cv)
    kp = generate_keypair()
    signed = sign_profile_root(record.profile_root, kp.private_key)
    tampered = signed.model_copy(update={"freshness_score": 1})
    with pytest.raises(SignatureError):
        verify_profile_root(tampered)


def test_swapping_pubkey_fails_verification(
    publisher: TalentPublisher, sample_cv: XTalentCV
) -> None:
    """pubkey is inside the signed payload — swapping it breaks the signature."""
    record = publisher.publish(sample_cv)
    kp1, kp2 = generate_keypair(), generate_keypair()
    signed = sign_profile_root(record.profile_root, kp1.private_key)

    swapped = signed.model_copy(update={"pubkey": kp2.public_key})
    with pytest.raises(SignatureError):
        verify_profile_root(swapped)


def test_corrupted_signature_fails(
    publisher: TalentPublisher, sample_cv: XTalentCV
) -> None:
    record = publisher.publish(sample_cv)
    kp = generate_keypair()
    signed = sign_profile_root(record.profile_root, kp.private_key)

    # Flip a byte in the base64 payload.
    sig = signed.signature
    assert sig is not None
    flipped_char = "A" if sig[-1] != "A" else "B"
    corrupted = signed.model_copy(update={"signature": sig[:-1] + flipped_char})
    with pytest.raises(SignatureError):
        verify_profile_root(corrupted)


def test_mismatched_pubkey_at_sign_time_raises(
    publisher: TalentPublisher, sample_cv: XTalentCV
) -> None:
    """Presetting the wrong pubkey on the root should fail before signing."""
    record = publisher.publish(sample_cv)
    kp, other = generate_keypair(), generate_keypair()
    preset = record.profile_root.model_copy(update={"pubkey": other.public_key})
    with pytest.raises(SignatureError, match="does not match"):
        sign_profile_root(preset, kp.private_key)


# ---------------------------------------------------------------------------
# Integration with TalentSearchIndex
# ---------------------------------------------------------------------------


def test_require_signatures_rejects_unsigned(
    publisher: TalentPublisher, sample_cv: XTalentCV
) -> None:
    index = TalentSearchIndex(require_signatures=True)
    record = publisher.publish(sample_cv)
    with pytest.raises(SignatureError):
        index.upsert(record)


def test_require_signatures_accepts_signed(
    publisher: TalentPublisher, sample_cv: XTalentCV
) -> None:
    index = TalentSearchIndex(require_signatures=True)
    record = publisher.publish(sample_cv)
    kp = generate_keypair()
    signed = sign_profile_root(record.profile_root, kp.private_key)
    index.upsert(PublishRecord(cid=record.cid, cv_markdown=record.cv_markdown, profile_root=signed))

    hits = index.search("x", k=5)
    assert len(hits) == 1
    assert hits[0].record.profile_root.pubkey == kp.public_key


def test_require_signatures_rejects_tampered_signed(
    publisher: TalentPublisher, sample_cv: XTalentCV
) -> None:
    index = TalentSearchIndex(require_signatures=True)
    record = publisher.publish(sample_cv)
    kp = generate_keypair()
    signed = sign_profile_root(record.profile_root, kp.private_key)
    tampered = signed.model_copy(update={"freshness_score": 0})
    with pytest.raises(SignatureError):
        index.upsert(
            PublishRecord(cid=record.cid, cv_markdown=record.cv_markdown, profile_root=tampered)
        )


def test_default_index_accepts_unsigned(
    publisher: TalentPublisher, sample_cv: XTalentCV
) -> None:
    """Signing is opt-in: the default index still accepts unsigned records."""
    index = TalentSearchIndex()
    index.upsert(publisher.publish(sample_cv))
    assert index.search("x", k=5)


# ---------------------------------------------------------------------------
# API integration
# ---------------------------------------------------------------------------


def test_api_publish_returns_501_when_require_signatures_enabled(
    sample_cv: XTalentCV,
) -> None:
    from fastapi.testclient import TestClient

    from xtalent.api import app, get_index, get_publisher
    from xtalent.publish import InMemoryIPFS

    require_index = TalentSearchIndex(require_signatures=True)
    req_publisher = TalentPublisher(ipfs=InMemoryIPFS())
    app.dependency_overrides[get_publisher] = lambda: req_publisher
    app.dependency_overrides[get_index] = lambda: require_index
    try:
        client = TestClient(app)
        resp = client.post("/publish", json={"cv_markdown": sample_cv.to_markdown()})
        assert resp.status_code == 501
        assert resp.json()["detail"]["error"]["code"] == "signed_publish_not_implemented"
    finally:
        app.dependency_overrides.clear()
