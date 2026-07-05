"""Resolve upload destination chats"""

from __future__ import annotations

from dataclasses import dataclass

from pyrogram.client import Client

from .exceptions import CliError
from .link_parser import normalize_chat_id


@dataclass(slots=True)
class ChatTarget:
    chat_id: int | str
    thread_id: int | None = None
    title: str = ""


def _split_thread(raw: str) -> tuple[str, int | None]:
    if "|" not in raw:
        return raw.strip(), None
    chat_ref, thread_ref = raw.split("|", 1)
    thread_ref = thread_ref.strip()
    if not thread_ref.lstrip("-").isdigit():
        raise CliError(f"Invalid topic id in chat target: {raw!r}")
    return chat_ref.strip(), int(thread_ref)


async def resolve_chat_target(client: Client, raw: str) -> ChatTarget:
    """Resolve and cache a chat before upload.

    Accepts: me, @username, -100..., or -100...|topic_id
    """
    chat_ref, thread_id = _split_thread(raw)

    if chat_ref.lower() == "me":
        return ChatTarget("me", thread_id, "Saved Messages")

    chat_key = normalize_chat_id(chat_ref)
    try:
        chat = await client.get_chat(chat_key)
    except Exception as exc:
        raise CliError(
            f"Cannot access chat {chat_ref!r} (resolved id: {chat_key}).\n"
            f"Telegram: {exc}\n\n"
            "Checklist:\n"
            "  • Log in with a USER account (--phone), not a bot token.\n"
            "  • This account must be a member/admin of the channel.\n"
            "  • Verify the id (forward a channel post to @getidsbot).\n"
            "  • Open the channel in Telegram with this account, then retry.\n"
            '  • On PowerShell quote the id: -c "-100xxxxxxxxxx"'
        ) from exc

    title = chat.title or chat.username or str(chat.id)
    if chat.id is None:
        raise CliError(f"Chat id missing for {title!r}.")
    resolved_id: int | str = chat.id
    chat_type = getattr(chat.type, "name", str(chat.type))

    if chat_type in {"CHANNEL", "SUPERGROUP", "GROUP", "FORUM"}:
        try:
            me = await client.get_me()
            if me.id is not None:
                member = await client.get_chat_member(resolved_id, me.id)
                status = getattr(member.status, "name", str(member.status))
                if status not in {"OWNER", "ADMINISTRATOR", "MEMBER"}:
                    raise CliError(
                        f"You are not a member of {title!r} ({resolved_id}). "
                        "Join the channel with this account first."
                    )
        except CliError:
            raise
        except Exception:
            # get_chat_member may fail on some chat types; get_chat success is enough.
            pass

    return ChatTarget(resolved_id, thread_id, title)
