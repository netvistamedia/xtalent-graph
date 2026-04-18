"""End-to-end tests against the FastAPI reference server."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from xtalent import XTalentCV
from xtalent.api import app, get_index, get_publisher
from xtalent.publish import InMemoryIPFS, TalentPublisher
from xtalent.search import TalentSearchIndex


@pytest.fixture
def client(sample_cv: XTalentCV) -> TestClient:
    # Fresh in-memory backends per test, via FastAPI dependency overrides.
    publisher = TalentPublisher(ipfs=InMemoryIPFS())
    index = TalentSearchIndex()
    app.dependency_overrides[get_publisher] = lambda: publisher
    app.dependency_overrides[get_index] = lambda: index
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_publish_then_search(client: TestClient, sample_cv: XTalentCV) -> None:
    resp = client.post("/publish", json={"cv_markdown": sample_cv.to_markdown()})
    assert resp.status_code == 200
    body = resp.json()
    cid = body["cid"]
    assert body["handle"] == "@ada"
    assert body["profile_root"]["latest_cid"] == cid

    resp = client.post("/search", json={"query": "distributed systems", "k": 3})
    assert resp.status_code == 200
    hits = resp.json()["hits"]
    assert len(hits) == 1
    assert hits[0]["record"]["profile_root"]["handle"] == "@ada"


def test_get_profile_and_cv(client: TestClient, sample_cv: XTalentCV) -> None:
    publish = client.post("/publish", json={"cv_markdown": sample_cv.to_markdown()})
    cid = publish.json()["cid"]

    profile = client.get("/profile/@ada")
    assert profile.status_code == 200
    assert profile.json()["latest_cid"] == cid

    cv = client.get(f"/cv/{cid}")
    assert cv.status_code == 200
    assert cv.headers["content-type"].startswith("text/markdown")
    assert "## Summary" in cv.text


def test_delete_profile_tombstones(client: TestClient, sample_cv: XTalentCV) -> None:
    client.post("/publish", json={"cv_markdown": sample_cv.to_markdown()})

    resp = client.request("DELETE", "/profile/@ada", json={"reason": "GDPR"})
    assert resp.status_code == 200
    assert resp.json() == {"handle": "@ada", "tombstoned": True}

    hits = client.post("/search", json={"query": "anything", "k": 5}).json()["hits"]
    assert hits == []


def test_publish_invalid_markdown_is_400(client: TestClient) -> None:
    resp = client.post("/publish", json={"cv_markdown": "not a cv"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "invalid_request"


def test_publish_stale_version_is_409(client: TestClient, sample_cv: XTalentCV) -> None:
    client.post("/publish", json={"cv_markdown": sample_cv.to_markdown()})
    resp = client.post("/publish", json={"cv_markdown": sample_cv.to_markdown()})
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"]["code"] == "conflict"
