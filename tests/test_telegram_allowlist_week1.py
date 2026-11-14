"""Pilot access is denied by default, including all commands and group chats."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.telegram_access import parse_allowed_user_ids
from telegram_bot.main import PilotAccessMiddleware


def test_empty_allowlist_rejects_everyone():
    assert parse_allowed_user_ids("") == frozenset()
    assert parse_allowed_user_ids(None) == frozenset()


def test_mixed_separators_are_accepted_and_deduplicated():
    assert parse_allowed_user_ids("123, 456;123\n789") == frozenset({123, 456, 789})


@pytest.mark.parametrize("value", ["abc", "-1", "0", "123, nope", "12.3", "１２３"])
def test_invalid_ids_are_rejected(value):
    with pytest.raises(ValueError):
        parse_allowed_user_ids(value)


@pytest.mark.asyncio
async def test_unauthorized_private_user_cannot_invoke_handler():
    handler = AsyncMock()
    event = SimpleNamespace(
        chat=SimpleNamespace(type="private"),
        from_user=SimpleNamespace(id=999),
        answer=AsyncMock(),
    )
    response = await PilotAccessMiddleware(frozenset({123}))(handler, event, {})
    assert response is None
    handler.assert_not_awaited()
    event.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_authorized_user_private_chat_works():
    handler = AsyncMock(return_value="ok")
    event = SimpleNamespace(
        chat=SimpleNamespace(type="private"),
        from_user=SimpleNamespace(id=123),
        answer=AsyncMock(),
    )
    response = await PilotAccessMiddleware(frozenset({123}))(handler, event, {})
    assert response == "ok"
    handler.assert_awaited_once()
    event.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_group_chat_is_never_allowed_even_for_owner():
    handler = AsyncMock()
    event = SimpleNamespace(
        chat=SimpleNamespace(type="supergroup"),
        from_user=SimpleNamespace(id=123),
        answer=AsyncMock(),
    )
    response = await PilotAccessMiddleware(frozenset({123}))(handler, event, {})
    assert response is None
    handler.assert_not_awaited()
    event.answer.assert_not_awaited()
