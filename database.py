from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, MAX_FSUB_CHANNELS

mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["forcesub_bot"]

fsub_col = db["fsub_channels"]       # {_id: channel_id, title, invite_link}
goal_col = db["goals"]               # {_id: channel_id, goal, count, status}
settings_col = db["settings"]        # start_file + batch_pending docs
links_col = db["links"]              # {_id: token, ids: [message ids in DB channel]}
deletes_col = db["pending_deletes"]  # {chat_id, file_msg_ids, notice_msg_id, token, due_at, done}
users_col = db["users"]              # {_id: user_id, joined}


# ---------- Force-sub channels ----------

async def get_fsub_channels():
    return [doc async for doc in fsub_col.find()]


async def get_fsub_count():
    return await fsub_col.count_documents({})


async def is_fsub_channel(chat_id: int) -> bool:
    return await fsub_col.find_one({"_id": chat_id}) is not None


async def add_fsub_channel(chat_id: int, title: str, invite_link: str) -> bool:
    if await get_fsub_count() >= MAX_FSUB_CHANNELS:
        return False
    await fsub_col.update_one(
        {"_id": chat_id},
        {"$set": {"title": title, "invite_link": invite_link}},
        upsert=True,
    )
    return True


async def remove_fsub_channel(chat_id: int):
    await fsub_col.delete_one({"_id": chat_id})
    await goal_col.delete_one({"_id": chat_id})


# ---------- Goals ----------

async def set_goal(chat_id: int, goal: int):
    await goal_col.update_one(
        {"_id": chat_id},
        {"$set": {"goal": goal, "count": 0, "status": "active"}},
        upsert=True,
    )


async def get_goal(chat_id: int):
    return await goal_col.find_one({"_id": chat_id})


async def increment_goal(chat_id: int):
    return await goal_col.find_one_and_update(
        {"_id": chat_id, "status": "active"},
        {"$inc": {"count": 1}},
        return_document=True,
    )


async def complete_goal(chat_id: int):
    await goal_col.update_one({"_id": chat_id}, {"$set": {"status": "completed"}})


# ---------- Single start file (/setfile) ----------

async def set_start_file(chat_id: int, message_id: int):
    await settings_col.update_one(
        {"_id": "start_file"},
        {"$set": {"chat_id": chat_id, "message_id": message_id}},
        upsert=True,
    )


async def get_start_file():
    return await settings_col.find_one({"_id": "start_file"})


# ---------- Batch links ----------

async def set_batch_pending(owner_id: int, first_id: int):
    await settings_col.update_one(
        {"_id": f"batch_{owner_id}"},
        {"$set": {"first_id": first_id}},
        upsert=True,
    )


async def get_batch_pending(owner_id: int):
    return await settings_col.find_one({"_id": f"batch_{owner_id}"})


async def clear_batch_pending(owner_id: int):
    await settings_col.delete_one({"_id": f"batch_{owner_id}"})


async def create_link(token: str, ids: list):
    await links_col.insert_one({"_id": token, "ids": ids})


async def get_link(token: str):
    return await links_col.find_one({"_id": token})


# ---------- Auto-delete (persistent) ----------

async def schedule_delete(chat_id: int, file_msg_ids: list, notice_msg_id: int, token: str, delay: int):
    await deletes_col.insert_one({
        "chat_id": chat_id,
        "file_msg_ids": file_msg_ids,
        "notice_msg_id": notice_msg_id,
        "token": token,
        "due_at": datetime.now(timezone.utc) + timedelta(seconds=delay),
        "done": False,
    })


async def get_due_deletes():
    now = datetime.now(timezone.utc)
    return [d async for d in deletes_col.find({"done": False, "due_at": {"$lte": now}})]


async def mark_delete_done(doc_id):
    await deletes_col.update_one({"_id": doc_id}, {"$set": {"done": True}})


# ---------- Users ----------

async def add_user(user_id: int):
    await users_col.update_one(
        {"_id": user_id},
        {"$setOnInsert": {"joined": datetime.now(timezone.utc)}},
        upsert=True,
    )


async def get_all_users():
    return [d["_id"] async for d in users_col.find({}, {"_id": 1})]


async def get_user_count():
    return await users_col.count_documents({})
