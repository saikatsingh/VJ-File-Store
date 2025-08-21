# ---------------------- Imports ----------------------
import os
import asyncio
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)

# Database & utils
from database.ia_filterdb import Media, Media2, Media3, Media4
from database.users_chats_db import db
from info import (
    OWNER_ID, OWNER_USERNAME, BOT_USERNAME,
    LOG_CHANNEL, UPI_ID, PAYMENT_INFO, PAYMENT_QR,
    ALLOW_SCREENSHOT_SHARE, PAYMENT_PROOF_USERNAME,
    PROOF_CHANNEL, FORCE_SUB_CHANNELS, SHORTLINK_API, SHORTLINK_URL,
)
from utils import get_shortlink, verify_user_token


# ---------------------- Helper Functions ----------------------

def is_owner(user_id: int) -> bool:
    """Check if the given user is the bot owner"""
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
# ---------------------- Force Subscribe Helper ----------------------

async def check_force_sub(client: Client, user_id: int) -> bool:
    """
    Check if user has joined all required channels.
    Returns True if joined, False if not.
    """
    try:
        if not FORCE_SUB_CHANNELS:
            return True

        for channel in FORCE_SUB_CHANNELS:
            try:
                member = await client.get_chat_member(channel, user_id)
                if member.status in ["kicked", "banned"]:
                    return False
            except Exception:
                return False
        return True
    except Exception:
        return False


async def force_sub_message():
    """Generate force-subscribe message with join buttons"""
    buttons = []
    for channel in FORCE_SUB_CHANNELS:
        buttons.append([InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{channel.lstrip('@')}")])
    buttons.append([InlineKeyboardButton("✅ I Joined", callback_data="check_fsub")])

    return "🚨 **You must join our channels to use this bot!**", InlineKeyboardMarkup(buttons)


# ---------------------- /start Command ----------------------

@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    user = message.from_user

    # Save user in DB
    await db.add_user(user.id, user.first_name)

    # Force-subscribe check
    if not await check_force_sub(client, user.id):
        text, markup = await force_sub_message()
        return await message.reply_text(text, reply_markup=markup)

    # If user used token link
    if len(message.command) > 1:
        token = message.command[1]
        file_id = await verify_user_token(token, user.id)
        if file_id:
            file = await Media.find_one({"file_id": file_id})
            if not file:
                file = await Media2.find_one({"file_id": file_id})
            if not file:
                file = await Media3.find_one({"file_id": file_id})
            if not file:
                file = await Media4.find_one({"file_id": file_id})

            if file:
                try:
                    return await message.reply_cached_media(
                        file.file_id,
                        caption=file.caption or ""
                    )
                except Exception:
                    return await message.reply_text("⚠️ File not found.")
        else:
            return await message.reply_text("❌ Invalid or expired link.")

    # Default start message
    buttons = [
        [InlineKeyboardButton("💎 Buy Premium", callback_data="buy_premium")],
        [InlineKeyboardButton("📢 Updates", url=f"https://t.me/{FORCE_SUB_CHANNELS[0].lstrip('@')}")],
    ]

    await message.reply_text(
        f"👋 Hello {user.mention},\n\n"
        "I am your **File Store Bot** 📂.\n\n"
        "➡️ Send me any file and I will give you a **shortened link** to share.\n"
        "➡️ Users can download only after joining required channels.",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )
# ---------------------- Membership Plans ----------------------

@Client.on_message(filters.command("plans") & filters.private)
async def plans_cmd(client: Client, message: Message):
    user = message.from_user

    # Force-subscribe check
    if not await check_force_sub(client, user.id):
        text, markup = await force_sub_message()
        return await message.reply_text(text, reply_markup=markup)

    buttons = [
        [
            InlineKeyboardButton("💳 1 Month - ₹99", callback_data="plan_1m"),
            InlineKeyboardButton("💳 3 Months - ₹249", callback_data="plan_3m")
        ],
        [
            InlineKeyboardButton("💳 6 Months - ₹449", callback_data="plan_6m"),
            InlineKeyboardButton("💳 12 Months - ₹799", callback_data="plan_12m")
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_home")]
    ]

    await message.reply_text(
        "**💎 Premium Membership Plans 💎**\n\n"
        "✅ Access all stored files without ads.\n"
        "✅ No waiting time.\n"
        "✅ Faster link access.\n\n"
        "**Choose your plan below 👇**",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ---------------------- Buy Premium Callback ----------------------

@Client.on_callback_query(filters.regex("^buy_premium$"))
async def cb_buy_premium(client: Client, query: CallbackQuery):
    user = query.from_user

    # Membership chart + screenshot share button
    buttons = [
        [
            InlineKeyboardButton("💳 1 Month - ₹99", callback_data="plan_1m"),
            InlineKeyboardButton("💳 3 Months - ₹249", callback_data="plan_3m")
        ],
        [
            InlineKeyboardButton("💳 6 Months - ₹449", callback_data="plan_6m"),
            InlineKeyboardButton("💳 12 Months - ₹799", callback_data="plan_12m")
        ],
        [InlineKeyboardButton("📸 Share Screenshot", url=f"https://t.me/{PAYMENT_PROOF_USERNAME}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_home")]
    ]

    await query.message.edit_text(
        "**💎 Premium Membership Plans 💎**\n\n"
        "📌 After payment, click 'Share Screenshot' to send payment proof.\n\n"
        "✅ UPI ID: `{}`\n".format(UPI_ID) +
        ("✅ Extra Info: {}\n".format(PAYMENT_INFO) if PAYMENT_INFO else ""),
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )
# ---------------------- Plan Selection ----------------------

@Client.on_callback_query(filters.regex("^plan_"))
async def cb_plan_select(client: Client, query: CallbackQuery):
    plan = query.data.split("_")[1]  # 1m, 3m, 6m, 12m
    user = query.from_user

    prices = {
        "1m": "₹99 (1 Month)",
        "3m": "₹249 (3 Months)",
        "6m": "₹449 (6 Months)",
        "12m": "₹799 (12 Months)"
    }

    price_text = prices.get(plan, "Unknown Plan")

    buttons = [
        [InlineKeyboardButton("📸 Share Screenshot", url=f"https://t.me/{PAYMENT_PROOF_USERNAME}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="buy_premium")]
    ]

    await query.message.edit_text(
        f"**💎 Selected Plan:** {price_text}\n\n"
        "✅ UPI ID: `{}`\n".format(UPI_ID) +
        ("✅ Extra Info: {}\n\n".format(PAYMENT_INFO) if PAYMENT_INFO else "\n") +
        "📌 Please complete the payment and click **Share Screenshot** button below "
        "to send payment proof.",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )


# ---------------------- Payment Screenshot Handler ----------------------

@Client.on_message(filters.private & filters.photo)
async def payment_screenshot_handler(client: Client, message: Message):
    user_id = message.from_user.id

    if not ALLOW_SCREENSHOT_SHARE:
        return

    caption = (
        f"📸 **Payment Proof Received**\n\n"
        f"👤 User: `{user_id}`\n"
        f"Username: @{message.from_user.username if message.from_user.username else 'N/A'}\n"
        f"Name: {message.from_user.first_name}\n\n"
        "⚠️ Please verify manually and update premium status."
    )

    try:
        await client.send_photo(
            chat_id=f"@{PAYMENT_PROOF_USERNAME}",
            photo=message.photo.file_id,
            caption=caption
        )
        await message.reply_text("✅ Screenshot received! Please wait for verification.")
    except Exception as e:
        logger.error(f"Failed to forward screenshot: {e}")
        await message.reply_text("❌ Failed to forward screenshot. Please try again.")
# ---------------------- Admin: Approve / Reject Payments ----------------------

@Client.on_message(filters.command("approve") & filters.user(OWNER_ID))
async def approve_payment(client: Client, message: Message):
    try:
        if len(message.command) < 3:
            await message.reply_text("⚠️ Usage: `/approve user_id days`")
            return

        user_id = int(message.command[1])
        days = int(message.command[2])

        expiry = datetime.utcnow() + timedelta(days=days)
        await add_premium_user(user_id, expiry)

        try:
            await client.send_message(
                user_id,
                f"🎉 Congratulations! You are now a **Premium User**.\n\n"
                f"✅ Valid till: `{expiry.strftime('%Y-%m-%d %H:%M:%S')}`"
            )
        except Exception as e:
            logger.warning(f"Couldn't notify user {user_id}: {e}")

        await message.reply_text(f"✅ Approved premium for `{user_id}` till {expiry}")
    except Exception as e:
        logger.error(f"Approve error: {e}")
        await message.reply_text("❌ Something went wrong while approving.")


@Client.on_message(filters.command("reject") & filters.user(OWNER_ID))
async def reject_payment(client: Client, message: Message):
    try:
        if len(message.command) < 2:
            await message.reply_text("⚠️ Usage: `/reject user_id`")
            return

        user_id = int(message.command[1])
        try:
            await client.send_message(
                user_id,
                "❌ Your premium request has been rejected.\n"
                "📌 Please contact admin if you think this is a mistake."
            )
        except Exception as e:
            logger.warning(f"Couldn't notify rejected user {user_id}: {e}")

        await message.reply_text(f"❌ Rejected premium request for `{user_id}`")
    except Exception as e:
        logger.error(f"Reject error: {e}")
        await message.reply_text("❌ Something went wrong while rejecting.")


# ---------------------- Check Premium Status ----------------------

@Client.on_message(filters.command("premium"))
async def premium_status(client: Client, message: Message):
    user_id = message.from_user.id
    premium = await get_premium_user(user_id)

    if not premium:
        await message.reply_text("⏳ You are not a premium user.\n\nUse /buy to upgrade.")
        return

    expiry = premium.get("expiry")
    await message.reply_text(
        f"💎 You are a **Premium User**.\n\n"
        f"✅ Valid till: `{expiry}`"
    )


# ---------------------- Revoke Premium ----------------------

@Client.on_message(filters.command("remove_premium") & filters.user(OWNER_ID))
async def remove_premium(client: Client, message: Message):
    try:
        if len(message.command) < 2:
            await message.reply_text("⚠️ Usage: `/remove_premium user_id`")
            return

        user_id = int(message.command[1])
        await remove_premium_user(user_id)

        try:
            await client.send_message(
                user_id,
                "⚠️ Your premium membership has been revoked by admin."
            )
        except Exception as e:
            logger.warning(f"Couldn't notify removed user {user_id}: {e}")

        await message.reply_text(f"✅ Removed premium for `{user_id}`")
    except Exception as e:
        logger.error(f"Remove premium error: {e}")
        await message.reply_text("❌ Something went wrong while removing premium.")
