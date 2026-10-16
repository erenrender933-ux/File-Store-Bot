from pyrogram import Client
from pyrogram.errors import UserNotParticipant, ChatAdminRequired
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_fsub_channels


async def get_missing_channels(client: Client, user_id: int) -> list:
    """Return force-sub channels the user has not joined yet."""
    missing = []
    for ch in await get_fsub_channels():
        try:
            await client.get_chat_member(ch["_id"], user_id)
        except UserNotParticipant:
            missing.append(ch)
        except ChatAdminRequired:
            # Bot is not admin in that channel, skip it
            continue
    return missing


def build_join_buttons(missing: list) -> InlineKeyboardMarkup:
    rows = []
    for index, ch in enumerate(missing, start=1):
        rows.append([InlineKeyboardButton(f"Join Channel {index}", url=ch["invite_link"])])
    rows.append([InlineKeyboardButton("🔄 Try Again", callback_data="verify")])
    return InlineKeyboardMarkup(rows)
