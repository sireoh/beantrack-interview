from typing import Any

import pytest
from fastapi.testclient import TestClient

from testing.fakes import tv_add_payload

RATING_URL = "/api/tvlist/tt0903747/rating"


def _entry(client: TestClient) -> dict[str, Any]:
    entries: list[dict[str, Any]] = client.get("/api/tvlist").json()["entries"]
    assert len(entries) == 1
    return entries[0]


def test_new_entry_is_unrated(alice: TestClient) -> None:
    alice.post("/api/tvlist/add", json=tv_add_payload())

    assert _entry(alice)["rating"] is None


def test_set_rating_returns_entry_and_shows_in_list(alice: TestClient) -> None:
    alice.post("/api/tvlist/add", json=tv_add_payload())

    response = alice.patch(RATING_URL, json={"rating": 7})

    assert response.status_code == 200, response.text
    assert response.json()["rating"] == 7
    assert response.json()["show"]["imdb"] == "tt0903747"
    assert _entry(alice)["rating"] == 7


@pytest.mark.parametrize("rating", [1, 10])
def test_bounds_are_accepted(alice: TestClient, rating: int) -> None:
    alice.post("/api/tvlist/add", json=tv_add_payload())

    assert alice.patch(RATING_URL, json={"rating": rating}).status_code == 200
    assert _entry(alice)["rating"] == rating


def test_null_clears_rating(alice: TestClient) -> None:
    alice.post("/api/tvlist/add", json=tv_add_payload())
    alice.patch(RATING_URL, json={"rating": 7})

    response = alice.patch(RATING_URL, json={"rating": None})

    assert response.status_code == 200, response.text
    assert response.json()["rating"] is None
    assert _entry(alice)["rating"] is None


def test_rating_leaves_status_and_progress_alone(alice: TestClient) -> None:
    alice.post("/api/tvlist/add", json=tv_add_payload(status="watching"))
    before = _entry(alice)

    alice.patch(RATING_URL, json={"rating": 9})

    after = _entry(alice)
    assert (after["status"], after["current_episode"]) == (
        before["status"],
        before["current_episode"],
    )


@pytest.mark.parametrize(
    "body",
    [
        {"rating": 0},
        {"rating": 11},
        {"rating": -1},
        {"rating": 7.5},
        {"rating": "7"},
        {"rating": True},
        {},
        {"rating": 7, "extra": 1},
    ],
)
def test_invalid_rating_is_422(alice: TestClient, body: dict[str, Any]) -> None:
    alice.post("/api/tvlist/add", json=tv_add_payload())
    alice.patch(RATING_URL, json={"rating": 5})

    assert alice.patch(RATING_URL, json=body).status_code == 422
    assert _entry(alice)["rating"] == 5  # unchanged


def test_show_not_on_list_is_404(alice: TestClient) -> None:
    response = alice.patch(RATING_URL, json={"rating": 7})

    assert response.status_code == 404
    assert response.json() == {"detail": "Show is not in your TV list"}


def test_show_only_on_someone_elses_list_is_404(alice: TestClient, bob: TestClient) -> None:
    bob.post("/api/tvlist/add", json=tv_add_payload())
    bob.patch(RATING_URL, json={"rating": 3})

    assert alice.patch(RATING_URL, json={"rating": 7}).status_code == 404
    assert _entry(bob)["rating"] == 3  # Bob's rating is untouched


def test_ratings_are_per_user(alice: TestClient, bob: TestClient) -> None:
    alice.post("/api/tvlist/add", json=tv_add_payload())
    bob.post("/api/tvlist/add", json=tv_add_payload())

    alice.patch(RATING_URL, json={"rating": 9})
    bob.patch(RATING_URL, json={"rating": 2})

    assert _entry(alice)["rating"] == 9
    assert _entry(bob)["rating"] == 2


def test_signed_out_is_401(client: TestClient) -> None:
    assert client.patch(RATING_URL, json={"rating": 7}).status_code == 401
