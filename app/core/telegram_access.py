"""Pure policy for the pilot Telegram bot. No Telegram SDK required."""
import re


def parse_allowed_user_ids(raw: str | None) -> frozenset[int]:
    """Explicit positive Telegram user IDs. Blank means nobody is allowed."""
    if not raw or not raw.strip():
        return frozenset()
    result = set()
    for token in re.split(r"[,;\s]+", raw.strip()):
        if not token or not token.isascii() or not token.isdecimal() or int(token) <= 0:
            raise ValueError("TELEGRAM_ALLOWED_USER_IDS must contain positive numeric Telegram user IDs")
        result.add(int(token))
    return frozenset(result)
