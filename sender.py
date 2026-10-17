import asyncio
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import DELETE_AFTER, SWEEP_INTERVAL, DB_CHANNEL_ID
from database import (
    get_start_file, get_link, schedule_delete,
    get_due_deletes, mark_delete_done,
)

COPYRIGHT_TEXT = (
    "<b><blockquote>⧗ Due to Copyright issues....</blockquote></b>\n"
    "<blockquote><b>›› Yᴏᴜʀ ғɪʟᴇs ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ᴡɪᴛʜɪɴ 10 Mɪɴᴜᴛᴇs. Sᴏ ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴛʜᴇᴍ ᴛᴏ ᴀɴʏ ᴏᴛʜᴇʀ ᴘʟᴀᴄᴇ ғᴏʀ ғᴜᴛᴜʀᴇ ᴀᴠᴀɪʟᴀʙɪʟɪᴛʏ..</blockquote></b>/n"
    "<b><blockquote>≡ ɴᴏᴛᴇ : ᴜsᴇ [ᴠʟᴄ ᴘʟᴀʏᴇʀ](https://play.google.com/store/apps/details?id=org.videolan.vlc) ᴏʀ [ᴍx ᴘʟᴀʏᴇʀ](https://play.google.com/store/apps/details?id=com.mxtech.videoplayer.ad) ᴛᴏ ᴡᴀᴛᴄʜ ᴛʜᴇ ᴇᴘɪsᴏᴅᴇs ᴡɪᴛʜ ɢᴏᴏᴅ ᴇxᴘᴇʀɪᴇɴᴄᴇ !.</blockquote></b>"
)

DELETED_TEXT = (
    "🗑 **Your file is successfully deleted.**\n\n"
    "Click the button below to get your file again."
)

    
def get_again_markup(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("📥 Get Your File Again", callback_data=f"getfile:{token}")]]
    )


async def resolve_source(token: str):
    """Return (from_chat_id, message_ids) for a token. 'start' = single /setfile file."""
    if token == "start":
        stored = await get_start_file()
        if not stored:
            return None, []
        return stored["chat_id"], [stored["message_id"]]

    link = await get_link(token)
    if not link:
        return None, []
    return DB_CHANNEL_ID, link["ids"]


async def send_file_flow(client: Client, chat_id: int, token: str = "start"):
    wait_msg = await client.send_message(chat_id, "Please Wait..")

    from_chat, ids = await resolve_source(token)
    if not ids:
        await wait_msg.edit_text("❌ File not found or link expired.")
        return

    try:
        sent_ids = []
        # Telegram allows max 100 messages per copy call
        for i in range(0, len(ids), 100):
            copied = await client.copy_messages(chat_id, from_chat, ids[i:i + 100])
            sent_ids += [m.id for m in copied if m]

        notice = await client.send_message(chat_id, COPYRIGHT_TEXT)
        await wait_msg.delete()

        await schedule_delete(chat_id, sent_ids, notice.id, token, DELETE_AFTER)
    except Exception as e:
        await wait_msg.edit_text(f"❌ Error: {e}")


async def process_due_deletes(client: Client):
    for item in await get_due_deletes():
        await mark_delete_done(item["_id"])

        if item["file_msg_ids"]:
            try:
                await client.delete_messages(item["chat_id"], item["file_msg_ids"])
            except Exception as e:
                print(f"File delete failed: {e}")

        try:
            await client.edit_message_text(
                item["chat_id"],
                item["notice_msg_id"],
                DELETED_TEXT,
                reply_markup=get_again_markup(item["token"]),
            )
        except Exception as e:
            print(f"Notice edit failed: {e}")


async def sweeper(client: Client):
    while True:
        try:
            await process_due_deletes(client)
        except Exception as e:
            print(f"Sweeper error: {e}")
        await asyncio.sleep(SWEEP_INTERVAL)
