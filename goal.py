from pyrogram import Client
from pyrogram.types import ChatJoinRequest
from database import increment_goal, complete_goal, get_goal


async def handle_join_request(client: Client, req: ChatJoinRequest, owner_id: int):
    chat_id = req.chat.id

    # Auto-approve so the user becomes a member (needed for the force-sub check)
    try:
        await client.approve_chat_join_request(chat_id, req.from_user.id)
    except Exception as e:
        print(f"Approve failed for {req.from_user.id} in {chat_id}: {e}")
        return

    # Count only while a goal is active for this channel
    goal_doc = await get_goal(chat_id)
    if not goal_doc or goal_doc.get("status") != "active":
        return

    updated = await increment_goal(chat_id)
    if updated and updated["count"] >= updated["goal"]:
        await complete_goal(chat_id)
        await client.send_message(
            owner_id,
            f"🎉 Goal completed!\n\n"
            f"Channel: {req.chat.title}\n"
            f"Target: {updated['goal']} join requests reached.",
        )


def progress_text(goal_doc: dict, title: str) -> str:
    if not goal_doc:
        return f"No goal set for {title}."
    percent = min(100, int(goal_doc["count"] * 100 / goal_doc["goal"]))
    return (
        f"📊 Goal Progress\n\n"
        f"Channel: {title}\n"
        f"Status: {goal_doc['status']}\n"
        f"Progress: {goal_doc['count']} / {goal_doc['goal']} ({percent}%)"
    )
