from dataclasses import dataclass
from re import match
from urllib.parse import parse_qs, urlparse

from .exceptions import CliError


@dataclass(slots=True)
class LinkRef:
    chat_id: int | str
    message_id: int


def _parse_range(value: str) -> list[int]:
    if "-" not in value:
        return [int(value)]
    start_s, end_s = value.split("-", 1)
    start = int(start_s)
    end = int(end_s)
    if start <= end:
        return list(range(start, end + 1))
    return list(range(end, start + 1))


def parse_tg_links(link: str) -> list[LinkRef]:
    link = link.strip()
    if link.startswith("https://t.me/"):
        m = match(
            r"https://t\.me/(?:c/)?([^/]+)/(?:\d+/)*([0-9-]+)$",
            link,
        )
        if not m:
            raise CliError(f"Invalid Telegram link format: {link}")
        chat = m.group(1)
        message_ids = _parse_range(m.group(2))
        if chat.isdigit() and "/c/" in link:
            chat_id: int | str = int(f"-100{chat}")
        elif chat.isdigit():
            chat_id = int(chat)
        else:
            chat_id = chat
        return [LinkRef(chat_id=chat_id, message_id=m_id) for m_id in message_ids]

    if link.startswith("tg://openmessage?"):
        parsed = urlparse(link)
        query = parse_qs(parsed.query)
        user_values = query.get("user_id", [])
        msg_values = query.get("message_id", [])
        if not user_values or not msg_values:
            raise CliError(f"Invalid tg://openmessage link: {link}")
        chat_id = int(user_values[0])
        message_ids = _parse_range(msg_values[0])
        return [LinkRef(chat_id=chat_id, message_id=m_id) for m_id in message_ids]

    if link.startswith("tg://privatepost?"):
        parsed = urlparse(link)
        query = parse_qs(parsed.query)
        channel_values = query.get("channel", [])
        post_values = query.get("post", [])
        if not channel_values or not post_values:
            raise CliError(f"Invalid tg://privatepost link: {link}")
        chat_id = int(f"-100{channel_values[0]}")
        message_ids = _parse_range(post_values[0])
        return [LinkRef(chat_id=chat_id, message_id=m_id) for m_id in message_ids]

    raise CliError(f"Unsupported Telegram link format: {link}")


def parse_tg_link(link: str) -> LinkRef:
    refs = parse_tg_links(link)
    if not refs:
        raise CliError(f"Invalid Telegram link format: {link}")
    return refs[0]


def normalize_chat_id(raw_id: str) -> int | str:
    value = str(raw_id).strip()
    if value.lstrip("-").isdigit():
        n = int(value)
        # Telegram supergroup/channel IDs are -100xxxxxxxxxx. Shells (esp. PowerShell)
        # often eat the leading "-" when passing "-c -100..." so we get a positive int.
        if n > 0 and str(n).startswith("100") and len(str(n)) >= 11:
            return -n
        return n
    return value
