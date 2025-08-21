import os
import time
import asyncio
import logging
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)

from config import (
    OWNER_ID,
    UPI_ID,
    PAYMENT_QR,
    PAYMENT_INFO,
    ALLOW_SCREENSHOT_SHARE,
    PAYMENT_PROOF_USERNAME
)

from database.users_db import add_user, get_user, get_all_users, update_user
from database.premium_db import add_premium_user, remove_premium_user, get_premium_user

logger = logging.getLogger(__name__)

# ---------------------- Helper Functions ----------------------

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def format_timedelta(td: timedelta) -> str:
    """Convert timedelta to human-readable string"""
    days = td.days
    hours, remainder = divmod(td.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


async def send_premium_plans(client: Client, message: Message):
    """Send premium membership plans with UPI + screenshot proof button"""
    buttons = [
        [InlineKeyboardButton("💎 1 Month - ₹99", callback_data="buy_30")],
        [InlineKeyboardButton("💎 3 Months - ₹249", callback_data="buy_90")],
        [InlineKeyboardButton("💎 1 Year - ₹799", callback_data="buy_365")],
        [InlineKeyboardButton("📤 Pay Now (UPI)", url=f"upi://pay?pa={UPI_ID}&pn=FileStoreBot")]
    ]

    # Screenshot proof button
    if ALLOW_SCREENSHOT_SHARE and PAYMENT_PROOF_USERNAME:
        buttons.append(
            [InlineKeyboardButton("📤 Share Screenshot", url=f"https://t.me/{PAYMENT_PROOF_USERNAME}")]
        )

    caption = (
        "💎 **Premium Membership Plans** 💎\n\n"
        f"{PAYMENT_INFO}\n\n"
        "✅ Pay via UPI / QR\n"
        "✅ Send screenshot as proof\n"
        "✅ Admin will activate your premium"
    )

    if PAYMENT_QR:
        await message.reply_photo(
            photo=PAYMENT_QR,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await message.reply_text(
            caption,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
# ---------------------- Commands ----------------------

@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        await add_user(message.from_user.id)

    buttons = [
        [InlineKeyboardButton("💎 Premium Plans", callback_data="show_plans")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help_menu")]
    ]

    await message.reply_text(
        f"👋 Hello {message.from_user.mention}!\n\n"
        "Welcome to **FileStore Bot** 📂\n\n"
        "⚡ Store your files & get sharable links\n"
        "💎 Unlock premium for unlimited access",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@Client.on_message(filters.command("help") & filters.private)
async def help_cmd(client: Client, message: Message):
    text = (
        "**📚 Help Menu**\n\n"
        "➤ /start - Start the bot\n"
        "➤ /plans - View premium plans\n"
        "➤ /id - Get your Telegram ID\n"
        "➤ /broadcast - Broadcast message (Owner only)\n"
        "➤ /add_premium <days> - Add premium to user (Owner only)\n"
        "➤ /remove_premium - Remove user from premium (Owner only)\n"
    )

    await message.reply_text(text)


@Client.on_message(filters.command("plans") & filters.private)
async def plans_cmd(client: Client, message: Message):
    await send_premium_plans(client, message)


@Client.on_message(filters.command("id") & filters.private)
async def id_cmd(client: Client, message: Message):
    await message.reply_text(
        f"👤 Your ID: `{message.from_user.id}`"
    )


# ---------------------- Premium Management ----------------------

@Client.on_message(filters.command("add_premium") & filters.private)
async def add_premium_cmd(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply_text("❌ You are not authorized.")

    try:
        args = message.text.split()
        user_id = int(args[1])
        days = int(args[2])
    except Exception:
        return await message.reply_text("Usage: `/add_premium user_id days`")

    expire_date = datetime.now() + timedelta(days=days)
    await add_premium_user(user_id, expire_date)

    await message.reply_text(
        f"✅ Premium activated for `{user_id}` for {days} days."
    )
    try:
        await client.send_message(
            user_id,
            f"🎉 You have been upgraded to **Premium** for {days} days!"
        )
    except Exception:
        pass


@Client.on_message(filters.command("remove_premium") & filters.private)
async def remove_premium_cmd(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply_text("❌ You are not authorized.")

    try:
        args = message.text.split()
        user_id = int(args[1])
    except Exception:
        return await message.reply_text("Usage: `/remove_premium user_id`")

    await remove_premium_user(user_id)
    await message.reply_text(f"✅ Premium removed from `{user_id}`")
    try:
        await client.send_message(
            user_id,
            "⚠️ Your premium membership has been removed."
        )
    except Exception:
        pass
# ---------------------- Payment & Proof System ----------------------

@Client.on_callback_query(filters.regex("^show_plans$"))
async def show_plans_cb(client: Client, query: CallbackQuery):
    await query.message.delete()
    await send_premium_plans(client, query.message)


async def send_premium_plans(client, message):
    plans_text = (
        "**💎 Premium Membership Plans**\n\n"
        "➡️ 30 Days - ₹99\n"
        "➡️ 90 Days - ₹249\n"
        "➡️ 180 Days - ₹449\n\n"
        "⚡ Pay via UPI QR below & send proof"
    )

    buttons = [
        [InlineKeyboardButton("📤 Share Screenshot", url=f"https://t.me/{OWNER_USERNAME}")],
        [InlineKeyboardButton("✅ I Have Paid", callback_data="paid_done")]
    ]

    try:
        await message.reply_photo(
            photo=UPI_QR_CODE,
            caption=plans_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception:
        await message.reply_text(
            plans_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )


@Client.on_callback_query(filters.regex("^paid_done$"))
async def paid_done_cb(client: Client, query: CallbackQuery):
    await query.answer("📤 Please send payment screenshot to admin", show_alert=True)


# ---------------------- Proof Channel Logger ----------------------

@Client.on_message(filters.photo & filters.private)
async def payment_proof_handler(client: Client, message: Message):
    user = message.from_user
    caption = (
        f"🧾 **Payment Proof Received**\n\n"
        f"👤 User: {user.mention}\n"
        f"🆔 ID: `{user.id}`\n"
        f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    if PROOF_CHANNEL:
        try:
            await client.send_photo(
                chat_id=PROOF_CHANNEL,
                photo=message.photo.file_id,
                caption=caption
            )
        except Exception as e:
            print("Error sending proof:", e)

    try:
        await client.send_message(
            OWNER_ID,
            f"📤 {user.mention} ne payment proof bheja hai. Check karo!"
        )
    except Exception:
        pass

    await message.reply_text(
        "✅ Screenshot received!\n\n"
        "⏳ Admin will verify & activate your premium soon."
    )
# ---------------------- Broadcast System ----------------------

BROADCAST_USERS = set()

@Client.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_handler(client: Client, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("❌ Reply to a message to broadcast.")

    sent = 0
    failed = 0

    async for user in db.get_all_users():
        try:
            await message.reply_to_message.copy(user["user_id"])
            sent += 1
            await asyncio.sleep(0.2)  # prevent flood
        except Exception:
            failed += 1
            continue

    await message.reply_text(f"✅ Broadcast done!\n\n📤 Sent: {sent}\n❌ Failed: {failed}")


# ---------------------- User Info / ID Command ----------------------

@Client.on_message(filters.command("id"))
async def id_cmd(client: Client, message: Message):
    if message.reply_to_message:
        user = message.reply_to_message.from_user
        await message.reply_text(
            f"👤 Name: {user.mention}\n🆔 ID: `{user.id}`"
        )
    else:
        await message.reply_text(
            f"👤 Name: {message.from_user.mention}\n🆔 ID: `{message.from_user.id}`"
        )


# ---------------------- Ban / Unban Users ----------------------

BANNED_USERS = set()

@Client.on_message(filters.command("ban") & filters.user(OWNER_ID))
async def ban_user(client: Client, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("❌ Reply to a user to ban.")

    user = message.reply_to_message.from_user
    BANNED_USERS.add(user.id)
    await db.ban_user(user.id)
    await message.reply_text(f"🚫 {user.mention} banned successfully.")


@Client.on_message(filters.command("unban") & filters.user(OWNER_ID))
async def unban_user(client: Client, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("❌ Reply to a user to unban.")

    user = message.reply_to_message.from_user
    if user.id in BANNED_USERS:
        BANNED_USERS.remove(user.id)
    await db.unban_user(user.id)
    await message.reply_text(f"✅ {user.mention} unbanned successfully.")


# ---------------------- Add / Remove Filters ----------------------

@Client.on_message(filters.command("add_filter") & filters.user(OWNER_ID))
async def add_filter(client: Client, message: Message):
    if len(message.command) < 3:
        return await message.reply_text("Usage: /add_filter keyword reply_text")

    keyword = message.command[1].lower()
    reply_text = " ".join(message.command[2:])
    await db.add_filter(keyword, reply_text)
    await message.reply_text(f"✅ Filter added for **{keyword}**")


@Client.on_message(filters.command("del_filter") & filters.user(OWNER_ID))
async def del_filter(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /del_filter keyword")

    keyword = message.command[1].lower()
    await db.del_filter(keyword)
    await message.reply_text(f"❌ Filter removed for **{keyword}**")


@Client.on_message(filters.command("filters"))
async def list_filters(client: Client, message: Message):
    filters_list = await db.list_filters()
    if not filters_list:
        return await message.reply_text("No filters found.")

    text = "**📑 Current Filters:**\n\n"
    for f in filters_list:
        text += f"• `{f['keyword']}` → {f['reply_text'][:30]}...\n"

    await message.reply_text(text)
# ---------------------- Search System with Pagination ----------------------

SEARCH_DATA = {}  # user_id: { "results": [], "page": 0 }

RESULTS_PER_PAGE = 10


@Client.on_message(filters.command("search"))
async def search_files(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /search keyword")

    query = " ".join(message.command[1:]).lower()
    results = await db.search_files(query)

    if not results:
        return await message.reply_text("❌ No results found.")

    SEARCH_DATA[message.from_user.id] = {"results": results, "page": 0}
    await send_search_page(client, message.chat.id, message.from_user.id)


async def send_search_page(client, chat_id, user_id):
    data = SEARCH_DATA.get(user_id)
    if not data:
        return

    results = data["results"]
    page = data["page"]

    start = page * RESULTS_PER_PAGE
    end = start + RESULTS_PER_PAGE
    current_results = results[start:end]

    text = f"🔍 **Search Results (Page {page+1})**\n\n"
    buttons = []

    for r in current_results:
        text += f"📂 {r['file_name']} ({r['file_size']})\n"
        buttons.append([InlineKeyboardButton(r['file_name'][:25], callback_data=f"get_{r['file_id']}")])

    nav_btns = []
    if page > 0:
        nav_btns.append(InlineKeyboardButton("⬅️ Prev", callback_data="prev"))
    if end < len(results):
        nav_btns.append(InlineKeyboardButton("Next ➡️", callback_data="next"))

    if nav_btns:
        buttons.append(nav_btns)

    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close")])

    await client.send_message(
        chat_id,
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )


# ---------------------- Callback Query for Pagination + File Fetch ----------------------

@Client.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data

    if data == "next":
        SEARCH_DATA[user_id]["page"] += 1
        await query.message.delete()
        await send_search_page(client, query.message.chat.id, user_id)

    elif data == "prev":
        SEARCH_DATA[user_id]["page"] -= 1
        await query.message.delete()
        await send_search_page(client, query.message.chat.id, user_id)

    elif data == "close":
        await query.message.delete()
        SEARCH_DATA.pop(user_id, None)

    elif data.startswith("get_"):
        file_id = data.split("_", 1)[1]
        file = await db.get_file_by_id(file_id)

        if not file:
            return await query.answer("❌ File not found in DB.", show_alert=True)

        await client.send_cached_media(
            chat_id=query.message.chat.id,
            file_id=file["file_id"],
            caption=f"📂 **{file['file_name']}**\n\n💾 Size: {file['file_size']}"
        )
        await query.answer("✅ File sent!", show_alert=False)


# ---------------------- PM Search Results ----------------------

@Client.on_message(filters.private & filters.text)
async def pm_search_handler(client: Client, message: Message):
    if message.from_user.id in BANNED_USERS:
        return await message.reply_text("🚫 You are banned from using this bot.")

    query = message.text.lower()
    results = await db.search_files(query)

    if not results:
        return await message.reply_text("❌ No results found.")

    SEARCH_DATA[message.from_user.id] = {"results": results, "page": 0}
    await send_search_page(client, message.chat.id, message.from_user.id)
