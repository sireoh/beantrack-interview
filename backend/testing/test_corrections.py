"""BT-1: catalogue corrections (admin-reviewed) and personal title/image overrides."""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import CorrectionStatus, ShowCorrection, TvShow, User
from app.services import corrections as corrections_service
from testing.conftest import LoginAs
from testing.fakes import tv_add_payload

BB = "tt0903747"  # Breaking Bad
WIRE = "tt0306414"  # The Wire
BB_TITLE = "Breaking Bad"
BB_IMAGE = "https://static.tvmaze.com/bb-original.jpg"
NEW_IMAGE = "https://img.example.com/bb-better.jpg"


@pytest.fixture
def carol(login_as: LoginAs) -> TestClient:
    return login_as("333333333333333333", "carol")


@pytest.fixture
def catalog(alice: TestClient, bob: TestClient) -> None:
    """Breaking Bad on alice's and bob's lists, The Wire on alice's."""
    assert alice.post("/api/tvlist/add", json=tv_add_payload(BB)).status_code == 201
    assert alice.post("/api/tvlist/add", json=tv_add_payload(WIRE)).status_code == 201
    assert bob.post("/api/tvlist/add", json=tv_add_payload(BB)).status_code == 201


def shown(client: TestClient, imdb: str = BB) -> tuple[str, str | None]:
    """(title, image) of a show as it appears in the client's own TV list."""
    entries = client.get("/api/tvlist").json()["entries"]
    show = next(e["show"] for e in entries if e["show"]["imdb"] == imdb)
    return show["title"], show["image"]


def submit(client: TestClient, **body: Any) -> Any:
    return client.post("/api/corrections", json={"imdb_id": BB, **body})


def shared_show(db: Session, imdb: str = BB) -> TvShow:
    db.expire_all()
    show = db.get(TvShow, imdb)
    assert show is not None
    return show


# --- auth -----------------------------------------------------------------------------

NEW_ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("POST", "/api/corrections", {"imdb_id": BB, "new_title": "x"}),
    ("GET", "/api/corrections/mine", None),
    ("GET", "/api/admin/corrections?status=pending", None),
    ("PATCH", "/api/admin/corrections/1/approve", None),
    ("PATCH", "/api/admin/corrections/1/reject", None),
    ("PUT", f"/api/tvlist/{BB}/override", {"custom_title": "x"}),
    ("DELETE", f"/api/tvlist/{BB}/override", None),
    ("GET", "/api/settings/custom-display", None),
    ("PUT", "/api/settings/custom-display", {"enabled": False}),
]
ADMIN_ROUTES = [r for r in NEW_ROUTES if r[1].startswith("/api/admin/")]


@pytest.mark.parametrize(("method", "url", "body"), NEW_ROUTES)
def test_signed_out_is_401(
    client: TestClient, method: str, url: str, body: dict[str, Any] | None
) -> None:
    response = client.request(method, url, json=body)

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.parametrize(("method", "url", "body"), ADMIN_ROUTES)
def test_admin_routes_are_403_for_regular_users(
    alice: TestClient, catalog: None, db: Session, method: str, url: str, body: Any
) -> None:
    correction_id = submit(alice, new_title="Hacked").json()["id"]

    response = alice.request(method, url.replace("/1/", f"/{correction_id}/"), json=body)

    assert response.status_code == 403
    assert shared_show(db).title == BB_TITLE
    assert db.get(ShowCorrection, correction_id).status == CorrectionStatus.PENDING  # type: ignore[union-attr]


# --- submitting -----------------------------------------------------------------------


def test_submit_creates_a_pending_correction(alice: TestClient, catalog: None) -> None:
    response = submit(alice, new_title="Breaking Bad (2008)", new_image=NEW_IMAGE)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["imdb_id"] == BB
    assert (body["new_title"], body["new_image"]) == ("Breaking Bad (2008)", NEW_IMAGE)
    assert (body["current_title"], body["current_image"]) == (BB_TITLE, BB_IMAGE)
    assert body["reviewed_at"] is None


def test_pending_correction_changes_nobodys_list(
    alice: TestClient, bob: TestClient, catalog: None, db: Session
) -> None:
    submit(alice, new_title="Pending Title", new_image=NEW_IMAGE)

    assert shown(alice) == (BB_TITLE, BB_IMAGE)  # not even the submitter's
    assert shown(bob) == (BB_TITLE, BB_IMAGE)
    progress = alice.patch(f"/api/tvlist/{BB}/status", json={"status": "watching"}).json()
    assert progress["show"]["title"] == BB_TITLE
    assert (shared_show(db).title, shared_show(db).image) == (BB_TITLE, BB_IMAGE)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"new_title": None, "new_image": None},
        {"new_title": ""},
        {"new_title": "   "},
        {"new_image": "javascript:alert(1)"},
        {"new_image": "not a url"},
        {"new_title": "x" * 256},
        {"new_title": "ok", "extra": 1},
    ],
)
def test_invalid_correction_body_is_422(
    alice: TestClient, catalog: None, body: dict[str, Any]
) -> None:
    assert submit(alice, **body).status_code == 422


@pytest.mark.parametrize("bad_id", ["123", "tt12", "abc", "tt123456", "tt123456789", "TT0903747", ""])
def test_invalid_imdb_id_is_422(alice: TestClient, catalog: None, bad_id: str) -> None:
    response = alice.post("/api/corrections", json={"imdb_id": bad_id, "new_title": "x"})
    assert response.status_code == 422


@pytest.mark.parametrize("bad_id", ["123", "tt12", "abc"])
def test_invalid_imdb_id_in_override_path_is_422(alice: TestClient, bad_id: str) -> None:
    assert alice.put(f"/api/tvlist/{bad_id}/override", json={"custom_title": "x"}).status_code == 422
    assert alice.delete(f"/api/tvlist/{bad_id}/override").status_code == 422


def test_unknown_imdb_id_is_404(alice: TestClient, catalog: None) -> None:
    for unknown in ("tt9999999", "tt99999999"):
        response = alice.post("/api/corrections", json={"imdb_id": unknown, "new_title": "x"})
        assert response.status_code == 404
        assert alice.put(f"/api/tvlist/{unknown}/override", json={"custom_title": "x"}).status_code == 404
        assert alice.delete(f"/api/tvlist/{unknown}/override").status_code == 404


def test_second_correction_updates_the_pending_one_in_place(
    alice: TestClient, catalog: None, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_time = datetime(2026, 1, 1, tzinfo=UTC)
    second_time = datetime(2026, 1, 2, tzinfo=UTC)
    monkeypatch.setattr(corrections_service, "utcnow", lambda: first_time)
    first = submit(alice, new_title="First", new_image=NEW_IMAGE)
    monkeypatch.setattr(corrections_service, "utcnow", lambda: second_time)
    second = submit(alice, new_title="Second")

    assert first.status_code == 201
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    # The new submission replaces the proposal as a whole.
    assert (second.json()["new_title"], second.json()["new_image"]) == ("Second", None)
    assert second.json()["created_at"].startswith("2026-01-02")
    rows = db.scalars(select(ShowCorrection).where(ShowCorrection.submitted_by == "111111111111111111")).all()
    assert len(rows) == 1
    assert rows[0].status == CorrectionStatus.PENDING


def test_new_correction_allowed_after_review(
    alice: TestClient, admin: TestClient, catalog: None
) -> None:
    first = submit(alice, new_title="First").json()
    admin.patch(f"/api/admin/corrections/{first['id']}/reject")

    again = submit(alice, new_title="Second")

    assert again.status_code == 201
    assert again.json()["id"] != first["id"]


def test_pending_rule_is_per_user_and_per_show(
    alice: TestClient, bob: TestClient, catalog: None, db: Session
) -> None:
    assert submit(alice, new_title="A").status_code == 201
    assert submit(bob, new_title="B").status_code == 201
    assert alice.post("/api/corrections", json={"imdb_id": WIRE, "new_title": "W"}).status_code == 201
    assert db.scalar(select(func.count()).select_from(ShowCorrection)) == 3


def test_partial_index_blocks_duplicate_pending_rows(
    alice: TestClient, catalog: None, db: Session
) -> None:
    """The database itself enforces the rule, not just the service."""
    submit(alice, new_title="A")
    with pytest.raises(Exception, match="UNIQUE"):
        db.execute(
            text(
                "INSERT INTO show_corrections (imdb_id, submitted_by, new_title, status, created_at)"
                " VALUES (:imdb, :user, 'dup', 'pending', '2026-01-01')"
            ),
            {"imdb": BB, "user": "111111111111111111"},
        )
    db.rollback()


def test_mine_returns_only_my_corrections(
    alice: TestClient, bob: TestClient, admin: TestClient, catalog: None
) -> None:
    rejected = submit(alice, new_title="Alice 1").json()
    admin.patch(f"/api/admin/corrections/{rejected['id']}/reject")
    submit(alice, new_title="Alice 2")
    submit(bob, new_title="Bob")

    mine = alice.get("/api/corrections/mine")

    assert mine.status_code == 200
    assert sorted((c["new_title"], c["status"]) for c in mine.json()) == [
        ("Alice 1", "rejected"),
        ("Alice 2", "pending"),
    ]
    assert [c["new_title"] for c in bob.get("/api/corrections/mine").json()] == ["Bob"]


# --- reviewing ------------------------------------------------------------------------


def test_admin_list_has_submitter_and_current_vs_proposed(
    alice: TestClient, admin: TestClient, catalog: None, db: Session
) -> None:
    alice_user = db.get(User, "111111111111111111")
    assert alice_user is not None
    alice_user.avatar = "abc123"
    db.commit()
    created = submit(alice, new_title="New", new_image=NEW_IMAGE).json()

    response = admin.get("/api/admin/corrections", params={"status": "pending"})

    assert response.status_code == 200
    [item] = response.json()
    assert item["id"] == created["id"]
    assert item["discord_id"] == "111111111111111111"
    assert item["username"] == "alice"
    assert item["avatar_url"] == "https://cdn.discordapp.com/avatars/111111111111111111/abc123.png"
    assert (item["current_title"], item["current_image"]) == (BB_TITLE, BB_IMAGE)
    assert (item["new_title"], item["new_image"]) == ("New", NEW_IMAGE)
    assert item["created_at"]
    assert item["status"] == "pending"


def test_admin_list_filters_by_status(
    alice: TestClient, bob: TestClient, admin: TestClient, catalog: None
) -> None:
    a = submit(alice, new_title="A").json()
    submit(bob, new_title="B")
    admin.patch(f"/api/admin/corrections/{a['id']}/reject")

    def titles(status: str | None) -> list[str]:
        params = {"status": status} if status else {}
        return [c["new_title"] for c in admin.get("/api/admin/corrections", params=params).json()]

    assert titles("pending") == ["B"]
    assert titles("rejected") == ["A"]
    assert titles("approved") == []
    assert titles(None) == ["A", "B"]
    assert admin.get("/api/admin/corrections", params={"status": "bogus"}).status_code == 422


def test_approval_updates_everyones_list(
    alice: TestClient, bob: TestClient, admin: TestClient, catalog: None, db: Session
) -> None:
    correction = submit(bob, new_title="Breaking Bad (2008)", new_image=NEW_IMAGE).json()

    response = admin.patch(f"/api/admin/corrections/{correction['id']}/approve")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "approved"
    assert body["reviewed_by"] == "999999999999999999"
    assert body["reviewed_at"] is not None
    assert shown(alice) == ("Breaking Bad (2008)", NEW_IMAGE)
    assert shown(bob) == ("Breaking Bad (2008)", NEW_IMAGE)
    show = shared_show(db)
    assert (show.title, show.image) == ("Breaking Bad (2008)", NEW_IMAGE)


def test_approval_copies_only_the_fields_that_are_set(
    alice: TestClient, admin: TestClient, catalog: None, db: Session
) -> None:
    correction = submit(alice, new_title="Title Only").json()

    admin.patch(f"/api/admin/corrections/{correction['id']}/approve")

    assert shown(alice) == ("Title Only", BB_IMAGE)


def test_approval_does_not_override_a_personal_override(
    alice: TestClient, bob: TestClient, admin: TestClient, catalog: None
) -> None:
    alice.put(f"/api/tvlist/{BB}/override", json={"custom_title": "My Name For It"})
    correction = submit(bob, new_title="Approved Title", new_image=NEW_IMAGE).json()

    admin.patch(f"/api/admin/corrections/{correction['id']}/approve")

    assert shown(alice) == ("My Name For It", NEW_IMAGE)  # her title, the new shared image
    assert shown(bob) == ("Approved Title", NEW_IMAGE)


def test_reject_leaves_the_show_unchanged(
    alice: TestClient, admin: TestClient, catalog: None, db: Session
) -> None:
    correction = submit(alice, new_title="Nope", new_image=NEW_IMAGE).json()

    response = admin.patch(f"/api/admin/corrections/{correction['id']}/reject")

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["reviewed_by"] == "999999999999999999"
    assert response.json()["reviewed_at"] is not None
    assert shown(alice) == (BB_TITLE, BB_IMAGE)
    assert (shared_show(db).title, shared_show(db).image) == (BB_TITLE, BB_IMAGE)


@pytest.mark.parametrize("first", ["approve", "reject"])
@pytest.mark.parametrize("second", ["approve", "reject"])
def test_reviewing_a_non_pending_correction_is_409(
    alice: TestClient, admin: TestClient, catalog: None, db: Session, first: str, second: str
) -> None:
    correction = submit(alice, new_title="Once").json()
    admin.patch(f"/api/admin/corrections/{correction['id']}/{first}")
    title_after_first = shared_show(db).title

    response = admin.patch(f"/api/admin/corrections/{correction['id']}/{second}")

    assert response.status_code == 409
    assert shared_show(db).title == title_after_first
    expected = CorrectionStatus.APPROVED if first == "approve" else CorrectionStatus.REJECTED
    db.expire_all()
    assert db.get(ShowCorrection, correction["id"]).status == expected  # type: ignore[union-attr]


def test_reviewing_an_unknown_correction_is_404(admin: TestClient) -> None:
    assert admin.patch("/api/admin/corrections/12345/approve").status_code == 404
    assert admin.patch("/api/admin/corrections/12345/reject").status_code == 404


# --- personal overrides ---------------------------------------------------------------


def test_override_is_shown_only_to_its_owner(
    alice: TestClient, bob: TestClient, catalog: None, db: Session
) -> None:
    response = alice.put(
        f"/api/tvlist/{BB}/override", json={"custom_title": "Mine", "custom_image": NEW_IMAGE}
    )

    assert response.status_code == 200, response.text
    entry = response.json()
    assert (entry["show"]["title"], entry["show"]["image"]) == ("Mine", NEW_IMAGE)
    assert (entry["show"]["catalog_title"], entry["show"]["catalog_image"]) == (BB_TITLE, BB_IMAGE)
    assert entry["override"] == {"custom_title": "Mine", "custom_image": NEW_IMAGE}
    assert entry["override_active"] is True
    assert shown(alice) == ("Mine", NEW_IMAGE)
    assert shown(alice, WIRE)[0] == "The Wire"  # other shows untouched
    assert shown(bob) == (BB_TITLE, BB_IMAGE)
    assert (shared_show(db).title, shared_show(db).image) == (BB_TITLE, BB_IMAGE)


def test_partial_override_falls_back_to_shared_values(alice: TestClient, catalog: None) -> None:
    alice.put(f"/api/tvlist/{BB}/override", json={"custom_image": NEW_IMAGE})
    assert shown(alice) == (BB_TITLE, NEW_IMAGE)


def test_put_override_replaces_the_previous_one(alice: TestClient, catalog: None) -> None:
    alice.put(f"/api/tvlist/{BB}/override", json={"custom_title": "One", "custom_image": NEW_IMAGE})
    alice.put(f"/api/tvlist/{BB}/override", json={"custom_title": "Two"})
    assert shown(alice) == ("Two", BB_IMAGE)


def test_override_disappears_when_custom_display_is_off(alice: TestClient, catalog: None) -> None:
    alice.put(f"/api/tvlist/{BB}/override", json={"custom_title": "Mine"})
    assert alice.get("/api/settings/custom-display").json() == {"enabled": True}

    off = alice.put("/api/settings/custom-display", json={"enabled": False})

    assert off.status_code == 200
    assert off.json() == {"enabled": False}
    assert alice.get("/api/settings/custom-display").json() == {"enabled": False}
    assert alice.get("/api/auth/me").json()["custom_display_enabled"] is False
    assert shown(alice) == (BB_TITLE, BB_IMAGE)
    entry = next(e for e in alice.get("/api/tvlist").json()["entries"] if e["show"]["imdb"] == BB)
    assert entry["override"] == {"custom_title": "Mine", "custom_image": None}  # kept, not applied
    assert entry["override_active"] is False

    alice.put("/api/settings/custom-display", json={"enabled": True})
    assert shown(alice) == ("Mine", BB_IMAGE)


def test_custom_display_setting_is_per_user(
    alice: TestClient, bob: TestClient, catalog: None
) -> None:
    bob.put(f"/api/tvlist/{BB}/override", json={"custom_title": "Bob's"})
    alice.put("/api/settings/custom-display", json={"enabled": False})
    assert shown(bob) == ("Bob's", BB_IMAGE)


def test_delete_override(alice: TestClient, catalog: None) -> None:
    alice.put(f"/api/tvlist/{BB}/override", json={"custom_title": "Mine"})

    assert alice.delete(f"/api/tvlist/{BB}/override").status_code == 204
    assert shown(alice) == (BB_TITLE, BB_IMAGE)
    assert alice.delete(f"/api/tvlist/{BB}/override").status_code == 204  # idempotent


def test_override_needs_the_show_on_your_list(carol: TestClient, catalog: None) -> None:
    """Breaking Bad is in the catalogue, but not on carol's list."""
    assert carol.put(f"/api/tvlist/{BB}/override", json={"custom_title": "x"}).status_code == 404


def test_removing_a_show_drops_its_override(alice: TestClient, catalog: None) -> None:
    alice.put(f"/api/tvlist/{BB}/override", json={"custom_title": "Mine"})
    alice.delete(f"/api/tvlist/{BB}")
    alice.post("/api/tvlist/add", json=tv_add_payload(BB))
    assert shown(alice) == (BB_TITLE, BB_IMAGE)


@pytest.mark.parametrize(
    "body", [{}, {"custom_title": None, "custom_image": None}, {"custom_image": "ftp://x"}]
)
def test_invalid_override_body_is_422(
    alice: TestClient, catalog: None, body: dict[str, Any]
) -> None:
    assert alice.put(f"/api/tvlist/{BB}/override", json=body).status_code == 422


# --- injection ------------------------------------------------------------------------

INJECTION = "'); DROP TABLE shows;--"
INJECTION_TVSHOWS = "'); DROP TABLE tvshows;--"


@pytest.mark.parametrize("payload", [INJECTION, INJECTION_TVSHOWS])
def test_sql_injection_is_stored_verbatim(
    alice: TestClient, bob: TestClient, admin: TestClient, catalog: None, db: Session, payload: str
) -> None:
    created = submit(alice, new_title=payload)
    assert created.status_code == 201
    assert created.json()["new_title"] == payload
    assert alice.get("/api/corrections/mine").json()[0]["new_title"] == payload
    assert admin.get("/api/admin/corrections").json()[0]["new_title"] == payload

    admin.patch(f"/api/admin/corrections/{created.json()['id']}/approve")
    alice.put(f"/api/tvlist/{WIRE}/override", json={"custom_title": payload})

    assert shown(bob) == (payload, BB_IMAGE)
    assert shown(alice, WIRE)[0] == payload
    # The catalogue table is intact and still holds both shows.
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(TvShow)) == 2
    assert shared_show(db).title == payload
    tables = set(db.scalars(text("SELECT name FROM sqlite_master WHERE type = 'table'")))
    assert {"tvshows", "show_corrections", "tv_overrides", "users"} <= tables
