import asyncio
import os
import secrets
import sys

from pyrogram import Client, filters, idle
from pyrogram.types import Message, CallbackQuery
from pyrogram.errors import ChatAdminRequired, PeerIdInvalid, FloodWait

from config import (
    API_ID, API_HASH, BOT_TOKEN, OWNER_ID, DB_CHANNEL_ID,
    MAX_FSUB_CHANNELS, BATCH_LIMIT,
)
from database import (
    add_fsub_channel, remove_fsub_channel, is_fsub_channel,
    get_fsub_channels, get_fsub_count, set_goal, get_goal,
    set_start_file, add_user, get_all_users, get_user_count,
    set_batch_pending, get_batch_pending, clear_batch_pending,
    create_link, get_link,
)
from forcesub import get_missing_channels, build_join_buttons
from goal import handle_join_request, progress_text
from sender import send_file_flow, sweeper

app = Client(
    "forcesub_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

is_owner = filters.user(OWNER_ID)

HELP_TEXT = (
    "🤖 **Commands**\n\n"
    "**User**\n"
    "/start - Get the file (join channels first)\n"
    "/help - Show this message\n\n"
    "**Owner**\n"
    "/setfile - Reply to a file with this to set the single start file\n"
    "Forward first DB msg, then last DB msg - bot batch link generate pannum\n"
    "/batchcancel - Cancel pending batch\n"
    "/addfsub `<channel_id>` - Add force-sub channel (max 6)\n"
    "/delfsub `<channel_id>` - Remove force-sub channel\n"
    "/fsublist - List force-sub channels\n"
    "/goalset `<channel_id> <goal>` - Set join request goal\n"
    "/goalstatus `<channel_id>` - Check goal progress\n"
    "/users - Total users\n"
    "/broadcast - Reply to a message to send to all users\n"
    "/restart - Restart the bot"
)


# ---------- User side ----------

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    await add_user(message.from_user.id)

    try:
        await message.delete()
    except Exception:
        pass

    token = message.command[1] if len(message.command) > 1 else "start"

    if token != "start" and not await get_link(token):
        return await client.send_message(message.chat.id, "❌ Invalid or expired link.")

    missing = await get_missing_channels(client, message.from_user.id)
    if missing:
        await client.send_message(
            message.chat.id,
            "❗ Please join all the channels below, then press **Try Again**.",
            reply_markup=build_join_buttons(missing, token),
        )
        return

    await send_file_flow(client, message.chat.id, token)


@app.on_message(filters.command("help") & filters.private)
async def help_handler(client: Client, message: Message):
    await message.reply_text(HELP_TEXT)


@app.on_callback_query(filters.regex(r"^verify:"))
async def verify_handler(client: Client, query: CallbackQuery):
    token = query.data.split(":", 1)[1]
    missing = await get_missing_channels(client, query.from_user.id)
    if missing:
        await query.answer("You have not joined all channels yet.", show_alert=True)
        await query.message.edit_reply_markup(build_join_buttons(missing, token))
        return
    await query.answer()
    await query.message.delete()
    await send_file_flow(client, query.message.chat.id, token)


@app.on_callback_query(filters.regex(r"^getfile:"))
async def getfile_handler(client: Client, query: CallbackQuery):
    token = query.data.split(":", 1)[1]
    missing = await get_missing_channels(client, query.from_user.id)
    if missing:
        await query.answer("Please join all channels first.", show_alert=True)
        await client.send_message(
            query.message.chat.id,
            "❗ Please join all the channels below, then press **Try Again**.",
            reply_markup=build_join_buttons(missing, token),
        )
        return
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass
    await send_file_flow(client, query.message.chat.id, token)


# ---------- Join requests ----------

@app.on_chat_join_request()
async def join_request_handler(client: Client, req):
    await handle_join_request(client, req, OWNER_ID)


# ---------- Owner: batch link ----------

@app.on_message(filters.private & is_owner & filters.forwarded)
async def batch_forward_handler(client: Client, message: Message):
    src = message.forward_from_chat
    msg_id = message.forward_from_message_id

    if not src or src.id != DB_CHANNEL_ID or not msg_id:
        return await message.reply_text(
            "❌ DB channel-la irundhu forward pannunga (forward source hidden-a irukka koodadhu)."
        )

    owner = message.from_user.id
    pending = await get_batch_pending(owner)

    if not pending:
        await set_batch_pending(owner, msg_id)
        return await message.reply_text(
            "✅ First message saved.\nIppo LAST message-ah DB channel-la irundhu forward pannunga."
        )

    first, last = sorted([pending["first_id"], msg_id])
    await clear_batch_pending(owner)

    if last - first + 1 > BATCH_LIMIT:
        return await message.reply_text(f"❌ Batch too big. Max {BATCH_LIMIT} files.")

    msgs = await client.get_messages(DB_CHANNEL_ID, list(range(first, last + 1)))
    existing = [m.id for m in msgs if m and not m.empty]
    if not existing:
        return await message.reply_text("❌ No files found in that range.")

    token = secrets.token_urlsafe(8)
    await create_link(token, existing)

    me = await client.get_me()
    link = f"https://t.me/{me.username}?start={token}"
    await message.reply_text(
        f"✅ Batch link ready!\n\nFiles: **{len(existing)}**\n\n{link}"
    )


@app.on_message(filters.command("batchcancel") & filters.private & is_owner)
async def batchcancel_cmd(client: Client, message: Message):
    await clear_batch_pending(message.from_user.id)
    await message.reply_text("🗑 Pending batch cancelled.")


# ---------- Owner: single file ----------

@app.on_message(filters.command("setfile") & filters.private & is_owner)
async def setfile_cmd(client: Client, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to a file message with `/setfile`.")
    await set_start_file(message.reply_to_message.chat.id, message.reply_to_message.id)
    await message.reply_text("✅ File set. /start ippo indha file varum.")


# ---------- Owner: force-sub ----------

@app.on_message(filters.command("addfsub") & filters.private & is_owner)
async def add_fsub_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/addfsub <channel_id>`")

    if await get_fsub_count() >= MAX_FSUB_CHANNELS:
        return await message.reply_text(f"❌ Maximum {MAX_FSUB_CHANNELS} force-sub channels allowed.")

    try:
        chat_id = int(message.command[1])
        chat = await client.get_chat(chat_id)
        link = await client.create_chat_invite_link(
            chat_id, creates_join_request=True, name="ForceSub"
        )
    except ValueError:
        return await message.reply_text("❌ Invalid channel id.")
    except (PeerIdInvalid, ChatAdminRequired):
        return await message.reply_text("❌ Make the bot admin with invite permission first.")

    await add_fsub_channel(chat_id, chat.title, link.invite_link)
    await message.reply_text(f"✅ Added **{chat.title}** as force-sub channel.")


@app.on_message(filters.command("delfsub") & filters.private & is_owner)
async def del_fsub_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/delfsub <channel_id>`")
    await remove_fsub_channel(int(message.command[1]))
    await message.reply_text("🗑 Removed from force-sub list.")


@app.on_message(filters.command("fsublist") & filters.private & is_owner)
async def fsub_list_cmd(client: Client, message: Message):
    channels = await get_fsub_channels()
    if not channels:
        return await message.reply_text("No force-sub channels set.")
    lines = [f"{i}. {c['title']} (`{c['_id']}`)" for i, c in enumerate(channels, 1)]
    await message.reply_text("📋 Force-sub channels:\n\n" + "\n".join(lines))


# ---------- Owner: goals ----------

@app.on_message(filters.command("goalset") & filters.private & is_owner)
async def goalset_cmd(client: Client, message: Message):
    if len(message.command) < 3:
        return await message.reply_text("Usage: `/goalset <channel_id> <goal>`")
    try:
        chat_id = int(message.command[1])
        goal = int(message.command[2])
    except ValueError:
        return await message.reply_text("❌ Channel id and goal must be numbers.")

    if goal <= 0:
        return await message.reply_text("❌ Goal must be greater than 0.")
    if not await is_fsub_channel(chat_id):
        return await message.reply_text("❌ Channel not in force-sub list. Add with /addfsub first.")

    await set_goal(chat_id, goal)
    await message.reply_text(f"🎯 Goal set to **{goal}** join requests. Counting started.")


@app.on_message(filters.command("goalstatus") & filters.private & is_owner)
async def goalstatus_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/goalstatus <channel_id>`")
    chat_id = int(message.command[1])
    goal_doc = await get_goal(chat_id)
    try:
        title = (await client.get_chat(chat_id)).title
    except Exception:
        title = str(chat_id)
    await message.reply_text(progress_text(goal_doc, title))


# ---------- Owner: users & broadcast ----------

@app.on_message(filters.command("users") & filters.private & is_owner)
async def users_cmd(client: Client, message: Message):
    await message.reply_text(f"👥 Total users: **{await get_user_count()}**")


@app.on_message(filters.command("broadcast") & filters.private & is_owner)
async def broadcast_cmd(client: Client, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to a message with `/broadcast`.")

    users = await get_all_users()
    status = await message.reply_text(f"📢 Broadcasting to {len(users)} users...")
    source = message.reply_to_message
    sent, failed = 0, 0

    for uid in users:
        try:
            await source.copy(uid)
            sent += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await source.copy(uid)
                sent += 1
            except Exception:
                failed += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await status.edit_text(f"✅ Broadcast done.\n\nSent: {sent}\nFailed: {failed}")


# ---------- Owner: restart ----------

@app.on_message(filters.command("restart") & filters.private & is_owner)
async def restart_cmd(client: Client, message: Message):
    await message.reply_text("🔄 Restarting...")
    await app.stop()
    os.execl(sys.executable, sys.executable, *sys.argv)


# ---------- Main ----------

async def main():
    await app.start()
    asyncio.create_task(sweeper(app))
    print("Bot started")
    await idle()
    await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
