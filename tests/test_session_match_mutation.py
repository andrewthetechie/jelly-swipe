"""Tests for session_match_mutation domain types and stub class."""

import pytest

from jellyswipe.services.session_match_mutation import (
    ApplySwipeResult,
    CatalogFacts,
    DeleteChanged,
    DeleteMatchResult,
    DeleteNoOp,
    SessionActor,
    SessionMatchMutation,
    SwipeAccepted,
    SwipeRejected,
    UndoChanged,
    UndoNoOp,
    UndoSwipeResult,
)


class TestSessionActor:
    def test_instantiation(self) -> None:
        actor = SessionActor(user_id="u1", session_id="s1", active_room="R1")
        assert actor.user_id == "u1"
        assert actor.session_id == "s1"
        assert actor.active_room == "R1"

    def test_frozen(self) -> None:
        actor = SessionActor(user_id="u1", session_id="s1", active_room="R1")
        with pytest.raises(AttributeError):
            actor.user_id = "u2"  # type: ignore[misc]

    def test_optional_fields(self) -> None:
        actor = SessionActor(user_id="u1", session_id=None, active_room=None)
        assert actor.session_id is None
        assert actor.active_room is None


class TestCatalogFacts:
    def test_instantiation(self) -> None:
        facts = CatalogFacts(title="Movie", thumb="/t.jpg")
        assert facts.title == "Movie"
        assert facts.thumb == "/t.jpg"

    def test_defaults(self) -> None:
        facts = CatalogFacts()
        assert facts.title is None
        assert facts.thumb is None

    def test_frozen(self) -> None:
        facts = CatalogFacts(title="Movie")
        with pytest.raises(AttributeError):
            facts.title = "Other"  # type: ignore[misc]


class TestSwipeResultTypes:
    def test_swipe_accepted(self) -> None:
        result = SwipeAccepted(match_created=True)
        assert result.match_created is True

    def test_swipe_rejected(self) -> None:
        result = SwipeRejected(reason="room_not_found")
        assert result.reason == "room_not_found"

    def test_apply_swipe_result_union(self) -> None:
        accepted: ApplySwipeResult = SwipeAccepted(match_created=False)
        rejected: ApplySwipeResult = SwipeRejected(reason="invalid")
        assert isinstance(accepted, SwipeAccepted)
        assert isinstance(rejected, SwipeRejected)


class TestUndoSwipeResultTypes:
    def test_undo_changed(self) -> None:
        result = UndoChanged(match_removed=True)
        assert result.match_removed is True

    def test_undo_no_op(self) -> None:
        result = UndoNoOp()
        assert result is not None

    def test_undo_swipe_result_union(self) -> None:
        changed: UndoSwipeResult = UndoChanged(match_removed=False)
        no_op: UndoSwipeResult = UndoNoOp()
        assert isinstance(changed, UndoChanged)
        assert isinstance(no_op, UndoNoOp)


class TestDeleteMatchResultTypes:
    def test_delete_changed(self) -> None:
        result = DeleteChanged()
        assert result is not None

    def test_delete_no_op(self) -> None:
        result = DeleteNoOp()
        assert result is not None

    def test_delete_match_result_union(self) -> None:
        changed: DeleteMatchResult = DeleteChanged()
        no_op: DeleteMatchResult = DeleteNoOp()
        assert isinstance(changed, DeleteChanged)
        assert isinstance(no_op, DeleteNoOp)


class TestSessionMatchMutation:
    def test_instantiation(self) -> None:
        mutation = SessionMatchMutation()
        assert mutation is not None

    @pytest.mark.anyio
    async def test_apply_swipe_raises_not_implemented(self) -> None:
        mutation = SessionMatchMutation()
        actor = SessionActor(user_id="u1", session_id="s1", active_room="R1")
        with pytest.raises(NotImplementedError):
            await mutation.apply_swipe(
                code="1234",
                actor=actor,
                media_id="m1",
                direction="right",
                catalog_facts=CatalogFacts(),
                uow=None,  # type: ignore[arg-type]
            )

    @pytest.mark.anyio
    async def test_undo_swipe_raises_not_implemented(self) -> None:
        mutation = SessionMatchMutation()
        actor = SessionActor(user_id="u1", session_id="s1", active_room="R1")
        with pytest.raises(NotImplementedError):
            await mutation.undo_swipe(
                code="1234",
                actor=actor,
                media_id="m1",
                uow=None,  # type: ignore[arg-type]
            )

    @pytest.mark.anyio
    async def test_delete_match_raises_not_implemented(self) -> None:
        mutation = SessionMatchMutation()
        actor = SessionActor(user_id="u1", session_id="s1", active_room="R1")
        with pytest.raises(NotImplementedError):
            await mutation.delete_match(
                actor=actor,
                media_id="m1",
                uow=None,  # type: ignore[arg-type]
            )
