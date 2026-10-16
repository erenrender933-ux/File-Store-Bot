import asyncio
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import DELETE_AFTER, SWEEP_INTERVAL
from database import (
    get_start_file, schedule_delete, get_due_deletes, mark_delete_done,
)

COPYRIGHT_TEXT = (
    "⚠️ **Due to copyright issues....**\n\n"
    "Your files will be deleted within **10 Minutes**. "
    "So please forward them to any other place for future availability."
)

DELETED_TEXT = (
    "🗑 **Your file is successfully deleted.**\n\n"
    "Click the button below to get your file again."
)


def get_again_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("📥 Get Your File Again", callback_data="getfile")]]
    )


async def send_file_flow(client: Client, chat_id: int):
    wait_msg = await client.send_message(chat_id, "⏳ Please Wait...")

    stored = await get_start_file()
    if not stored:
        await wait_msg.edit_text("❌ No file set yet. Owner: use `/setfile`.")
        return

    try:
        file_msg = await client.copy_message(
            chat_id, stored["chat_id"], stored["message_id"]
        )
        notice = await client.send_message(chat_id, COPYRIGHT_TEXT)
        await wait_msg.delete()

        # Saved in MongoDB, so it survives bot restarts
        await schedule_delete(chat_id, file_msg.id, notice.id, DELETE_AFTER)
    except Exception as e:
        await wait_msg.edit_text(f"❌ Error: {e}")


async def process_due_deletes(client: Client):
    for item in await get_due_deletes():
        # Mark first so the same item is never processed twice
        await mark_delete_done(item["_id"])

        try:
            await client.delete_messages(item["chat_id"], item["file_msg_id"])
        except Exception as e:
            print(f"File delete failed: {e}")

        try:
            await client.edit_message_text(
                item["chat_id"],
                item["notice_msg_id"],
                DELETED_TEXT,
                reply_markup=get_again_markup(),
            )
        except Exception as e:
            print(f"Notice edit failed: {e}")


async def sweeper(client: Client):
    """Background loop: checks for due deletes every SWEEP_INTERVAL seconds."""
    while True:
        try:
            await process_due_deletes(client)
        except Exception as e:
            print(f"Sweeper error: {e}")
        await asyncio.sleep(SWEEP_INTERVAL)
