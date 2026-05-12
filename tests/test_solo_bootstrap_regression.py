"""End-to-end regression test: POST /room {solo:true} then SSE bootstrap.

Reproduces the issue-81 regression: solo mode returns to host page because
the SSE bootstrap event never fires (or fires without ready=true), so the
client never calls loadMovies().
"""

import json
import os

from tests.conftest import set_session_cookie


def _set_session_room(client, code, user_id="verified-user"):
    set_session_cookie(
        client,
        {
            "active_room": code,
            "my_user_id": user_id,
            "jf_delegate_server_identity": True,
            "solo_mode": True,
        },
        os.environ["FLASK_SECRET"],
    )


def _parse_first_sse_event(text: str) -> dict:
    """Parse the first SSE event 'data:' line as JSON."""
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[len("data:") :].strip())
    raise AssertionError(f"No data: line in SSE text: {text!r}")


def test_solo_room_create_then_stream_yields_ready_bootstrap(client, monkeypatch):
    """Solo mode end-to-end: POST /room {solo: true} → GET /room/{code}/stream

    First yielded event must be session_bootstrap with ready=True so the
    client knows to call loadMovies() instead of staying on the host page.
    """
    from starlette.requests import Request as StarletteRequest

    call_count = [0]

    async def fake_is_disconnected(self):
        call_count[0] += 1
        return call_count[0] >= 1

    monkeypatch.setattr(StarletteRequest, "is_disconnected", fake_is_disconnected)

    create_resp = client.post(
        "/room",
        json={"movies": True, "tv_shows": False, "solo": True},
    )
    assert create_resp.status_code == 200, create_resp.text
    code = create_resp.json()["pairing_code"]

    _set_session_room(client, code)

    resp = client.get(f"/room/{code}/stream")
    assert resp.status_code == 200, resp.text

    bootstrap = _parse_first_sse_event(resp.text)
    assert bootstrap["event_type"] == "session_bootstrap", bootstrap
    assert bootstrap["ready"] is True, (
        f"Solo room must bootstrap with ready=True so the client loads the deck, "
        f"got: {bootstrap}"
    )
    assert bootstrap["solo"] is True, bootstrap


def test_deck_response_uses_media_id_and_app_js_uses_it_for_trailer_cast(client):
    """Deck contract is `media_id` (not `id`), and app.js must use it.

    Regression: app.js called `/get-trailer/${m.id}` and `/cast/${m.id}`,
    but the deck endpoint returns items with `media_id` only (no `id`).
    So `m.id` was undefined, the URL became `/get-trailer/undefined`, the
    route failed to resolve the item, and the user saw "TRAILER NOT FOUND"
    for every card.
    """
    from pathlib import Path

    create_resp = client.post(
        "/room",
        json={"movies": True, "tv_shows": False, "solo": True},
    )
    assert create_resp.status_code == 200, create_resp.text
    code = create_resp.json()["pairing_code"]

    deck_resp = client.get(f"/room/{code}/deck")
    assert deck_resp.status_code == 200, deck_resp.text
    items = deck_resp.json()
    assert items, "deck should not be empty"
    first = items[0]
    assert "media_id" in first and first["media_id"], first

    # Verify the client uses `m.media_id` (not `m.id`) for trailer/cast lookups
    app_js = Path(__file__).resolve().parent.parent / "jellyswipe" / "static" / "app.js"
    src = app_js.read_text()
    assert "/get-trailer/${m.id}" not in src, (
        "app.js still constructs /get-trailer/${m.id}; m.id is undefined "
        "because the deck API returns media_id. Use m.media_id."
    )
    assert "/cast/${m.id}" not in src, (
        "app.js still constructs /cast/${m.id}; m.id is undefined because "
        "the deck API returns media_id. Use m.media_id."
    )
    assert "watchTrailer(event, m.id," not in src, (
        "watchTrailer is being passed m.id (undefined). Pass m.media_id."
    )
