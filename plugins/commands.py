# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import os
import logging
import random
import asyncio
import base64
import json
import re
from datetime import datetime, timedelta
from urllib.parse import quote_plus

from pyrogram import Client, filters, enums
from pyrogram.errors import ChatAdminRequired, FloodWait, UserNotParticipant
from pyrogram.types import *
from validators import domain

from Script import script
from plugins.dbusers import db
from plugins.users_api import get_user, update_user_info

from utils import verify_user, check_token, check_verification, get_token
from config import *
from TechVJ.utils.file_properties import get_name, get_hash, get_media_file_size

logger = logging.getLogger(__name__)

BATCH_FILES = {}

# ==========================
# Multi Force-Subscribe Helper
# ==========================
FSUB_TEXT = globals().get(
    "FSUB_TEXT",
    "⚠️ Pehle zaruri channels join karo, phir niche 'Refresh' dabao."
)

async def _safe_invite_link(client: Client, channel_id: int):
    """
    Try to get an invite link. If export fails (bot not admin) but channel is public,
    fallback to https://t.me/username. If nothing works, returns None.
    """
    try:
        chat = await client.get_chat(channel_id)
        if chat.invite_link:
            return chat.title, chat.invite_link
        try:
            link = await client.export_chat_invite_link(channel_id)
            return chat.title, link
        except Exception:
            if chat.username:
                return chat.title, f"https://t.me/{chat.username}"
            return chat.title, None
    except Exception:
        return "Channel", None

async def check_force_subscribe(client: Client, user_id: int):
    """
    Checks if user joined ALL FORCE_SUB_CHANNELS.
    Returns (True, None) if all joined.
    Else returns (False, InlineKeyboardMarkup) with join buttons + refresh.
    """
    fsubs = globals().get("FORCE_SUB_CHANNELS", []) or globals().get("FORCE_CHANNELS", [])
    if not fsubs:
        return True, None

    need_join = []
    for ch_id in fsubs:
        title, link = await _safe_invite_link(client, ch_id)
        try:
            member = await client.get_chat_member(ch_id, user_id)
            status = getattr(member, "status", "")
            if status in ("left", "kicked"):
                need_join.append((title, link))
        except UserNotParticipant:
            need_join.append((title, link))
        except Exception:
            need_join.append((title, link))

    if not need_join:
        return True, None

    rows = []
    for title, link in need_join:
        if link:
            rows.append([InlineKeyboardButton(f"Join {title}", url=link)])
        else:
            rows.append([InlineKeyboardButton(f"Join {title} (link unavailable)", url="https://t.me/")])
    rows.append([InlineKeyboardButton("🔄 Refresh", callback_data="refresh_fsub")])
    return False, InlineKeyboardMarkup(rows)

# ==========================
# Helpers
# ==========================
def get_size(size):
    """Get size in readable format"""
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

def formate_file_name(file_name):
    chars = ["[", "]", "(", ")"]
    for c in chars:
        file_name.replace(c, "")
    file_name = '@VJ_Botz ' + ' '.join(filter(lambda x: not x.startswith('http') and not x.startswith('@') and not x.startswith('www.'), file_name.split()))
    return file_name

# ==========================
# Premium Helpers
# ==========================
def _now_ts() -> int:
    return int(datetime.utcnow().timestamp())

async def is_premium(user_id: int) -> bool:
    """
    Check premium by reading user profile (plugins.users_api storage).
    Field: premium_expiry -> unix timestamp (UTC)
    """
    try:
        user = await get_user(user_id)
    except Exception:
        return False
    exp = user.get("premium_expiry")
    if not exp:
        return False
    try:
        return int(exp) > _now_ts()
    except Exception:
        return False

async def set_premium(user_id: int, days: int):
    expiry_ts = _now_ts() + int(days) * 86400
    await update_user_info(user_id, {"premium_expiry": expiry_ts})

async def remove_premium(user_id: int):
    await update_user_info(user_id, {"premium_expiry": 0})

def premium_badge(is_prem: bool) -> str:
    return "💎 Premium" if is_prem else "👤 Free"

def buy_premium_keyboard():
    rows = []
    if PREMIUM_ENABLED:
        rows.append([InlineKeyboardButton(BUY_PREMIUM_BUTTON_TEXT, callback_data="buy_premium")])
    return rows

def premium_payment_keyboard():
    rows = [
        [InlineKeyboardButton("📎 Payment Proof", url=PREMIUM_PAYMENT_PROOF_CHANNEL)],
        [InlineKeyboardButton("📤 SHARE SCREENSHOT", url=f"https://t.me/{PREMIUM_PAYMENT_CONTACT_ID}")],
        [InlineKeyboardButton("⬅️ BACK", callback_data="start")]
    ]
    return InlineKeyboardMarkup(rows)

# ==========================
# /start
# ==========================
@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    username = client.me.username

    # ---- FSub check ----
    ok, kb = await check_force_subscribe(client, message.from_user.id)
    if not ok:
        return await message.reply_text(FSUB_TEXT, reply_markup=kb, disable_web_page_preview=True)
    # ---------------------

    # Add user to DB if new
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(LOG_CHANNEL, script.LOG_TEXT.format(message.from_user.id, message.from_user.mention))

    # Deep-link?
    if len(message.command) != 2:
        # Normal /start
        prem = await is_premium(message.from_user.id)
        buttons = [[
            InlineKeyboardButton('💝 sᴜʙsᴄʀɪʙᴇ ᴍʏ ʏᴏᴜᴛᴜʙᴇ ᴄʜᴀɴɴᴇʟ', url='https://youtube.com/@Tech_VJ')
        ],[
            InlineKeyboardButton('🔍 sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url='https://t.me/vj_bot_disscussion'),
            InlineKeyboardButton('🤖 ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ', url='https://t.me/vj_botz')
        ],[
            InlineKeyboardButton('💁‍♀️ ʜᴇʟᴘ', callback_data='help'),
            InlineKeyboardButton('😊 ᴀʙᴏᴜᴛ', callback_data='about')
        ]]

        # Buy Premium button
        buttons += buy_premium_keyboard()

        if CLONE_MODE == True:
            buttons.append([InlineKeyboardButton('🤖 ᴄʀᴇᴀᴛᴇ ʏᴏᴜʀ ᴏᴡɴ ᴄʟᴏɴᴇ ʙᴏᴛ', callback_data='clone')])

        reply_markup = InlineKeyboardMarkup(buttons)
        me = client.me
        caption = script.START_TXT.format(message.from_user.mention, me.mention)
        caption += f"\n\nStatus: <b>{premium_badge(prem)}</b>"
        return await message.reply_photo(photo=random.choice(PICS), caption=caption, reply_markup=reply_markup)

    # deep-link or file token path
    data = message.command[1]
    try:
        pre, file_id = data.split('_', 1)
    except:
        file_id = data
        pre = ""

    # -------------------- VERIFY FLOW --------------------
    if data.split("-", 1)[0] == "verify":
        userid = data.split("-", 2)[1]
        token = data.split("-", 3)[2]

        # FSub check again (safety)
        ok, kb = await check_force_subscribe(client, message.from_user.id)
        if not ok:
            return await message.reply_text(FSUB_TEXT, reply_markup=kb, disable_web_page_preview=True)

        if str(message.from_user.id) != str(userid):
            return await message.reply_text(text="<b>Invalid link or Expired link !</b>", protect_content=True)

        is_valid = await check_token(client, userid, token)
        if is_valid == True:
            await message.reply_text(
                text=f"<b>Hey {message.from_user.mention}, You are successfully verified !\nNow you have unlimited access for all files till today midnight.</b>",
                protect_content=True
            )
            await verify_user(client, userid, token)
        else:
            return await message.reply_text(text="<b>Invalid link or Expired link !</b>", protect_content=True)
        return
    # ----------------------------------------------------

    # -------------------- BATCH FLOW --------------------
    if data.split("-", 1)[0] == "BATCH":
        # FSub check
        ok, kb = await check_force_subscribe(client, message.from_user.id)
        if not ok:
            return await message.reply_text(FSUB_TEXT, reply_markup=kb, disable_web_page_preview=True)

        # PREMIUM bypass verification
        user_is_premium = await is_premium(message.from_user.id)

        try:
            if not user_is_premium and (not await check_verification(client, message.from_user.id) and VERIFY_MODE == True):
                btn = [[
                    InlineKeyboardButton("Verify", url=await get_token(client, message.from_user.id, f"https://telegram.me/{username}?start="))
                ],[
                    InlineKeyboardButton("How To Open Link & Verify", url=VERIFY_TUTORIAL)
                ]]
                # Add Buy Premium button below verify UI
                btn += buy_premium_keyboard()
                await message.reply_text(
                    text="<b>You are not verified !\nKindly verify to continue !</b>",
                    protect_content=True,
                    reply_markup=InlineKeyboardMarkup(btn)
                )
                return
        except Exception as e:
            return await message.reply_text(f"**Error - {e}**")

        sts = await message.reply("**🔺 ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ**")
        file_id = data.split("-", 1)[1]
        msgs = BATCH_FILES.get(file_id)
        if not msgs:
            decode_file_id = base64.urlsafe_b64decode(file_id + "=" * (-len(file_id) % 4)).decode("ascii")
            msg = await client.get_messages(LOG_CHANNEL, int(decode_file_id))
            media = getattr(msg, msg.media.value)
            file_id = media.file_id
            file = await client.download_media(file_id)
            try:
                with open(file) as file_data:
                    msgs = json.loads(file_data.read())
            except:
                await sts.edit("FAILED")
                return await client.send_message(LOG_CHANNEL, "UNABLE TO OPEN FILE.")
            os.remove(file)
            BATCH_FILES[file_id] = msgs

        filesarr = []
        for msg in msgs:
            channel_id = int(msg.get("channel_id"))
            msgid = msg.get("msg_id")
            info = await client.get_messages(channel_id, int(msgid))
            if info.media:
                file_type = info.media
                file = getattr(info, file_type.value)
                f_caption = getattr(info, 'caption', '')
                if f_caption:
                    f_caption = f_caption.html
                old_title = getattr(file, "file_name", "")
                title = formate_file_name(old_title)
                size = get_size(int(file.file_size))
                if BATCH_FILE_CAPTION:
                    try:
                        f_caption = BATCH_FILE_CAPTION.format(
                            file_name='' if title is None else title,
                            file_size='' if size is None else size,
                            file_caption='' if f_caption is None else f_caption
                        )
                    except:
                        f_caption = f_caption
                if f_caption is None:
                    f_caption = f"{title}"

                reply_markup = None
                if STREAM_MODE == True:
                    if info.video or info.document:
                        log_msg = info
                        stream = f"{URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                        download = f"{URL}{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                        button = [[
                            InlineKeyboardButton("• ᴅᴏᴡɴʟᴏᴀᴅ •", url=download),
                            InlineKeyboardButton('• ᴡᴀᴛᴄʜ •', url=stream)
                        ],[
                            InlineKeyboardButton("• ᴡᴀᴛᴄʜ ɪɴ ᴡᴇʙ ᴀᴘᴘ •", web_app=WebAppInfo(url=stream))
                        ]]
                        reply_markup = InlineKeyboardMarkup(button)

                try:
                    msg = await info.copy(
                        chat_id=message.from_user.id,
                        caption=f_caption,
                        protect_content=False,
                        reply_markup=reply_markup
                    )
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    msg = await info.copy(
                        chat_id=message.from_user.id,
                        caption=f_caption,
                        protect_content=False,
                        reply_markup=reply_markup
                    )
                except:
                    continue
            else:
                try:
                    msg = await info.copy(chat_id=message.from_user.id, protect_content=False)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    msg = await info.copy(chat_id=message.from_user.id, protect_content=False)
                except:
                    continue
            filesarr.append(msg)
            await asyncio.sleep(1)
        await sts.delete()
        if AUTO_DELETE_MODE == True:
            k = await client.send_message(
                chat_id=message.from_user.id,
                text=f"<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\nThis Movie File/Video will be deleted in <b><u>{AUTO_DELETE} minutes</u> 🫥 <i></b>(Due to Copyright Issues)</i>.\n\n<b><i>Please forward this File/Video to your Saved Messages and Start Download there</b>"
            )
            await asyncio.sleep(AUTO_DELETE_TIME)
            for x in filesarr:
                try:
                    await x.delete()
                except:
                    pass
            await k.edit_text("<b>Your All Files/Videos is successfully deleted!!!</b>")
        return
    # ----------------------------------------------------

    # -------------------- SINGLE FILE FLOW --------------------
    try:
        pre, decode_file_id = (
            (base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("ascii")
        ).split("_", 1)
    except Exception:
        return

    # FSub check
    ok, kb = await check_force_subscribe(client, message.from_user.id)
    if not ok:
        return await message.reply_text(FSUB_TEXT, reply_markup=kb, disable_web_page_preview=True)

    # PREMIUM bypass verification
    user_is_premium = await is_premium(message.from_user.id)

    if not user_is_premium and (not await check_verification(client, message.from_user.id) and VERIFY_MODE == True):
        btn = [[
            InlineKeyboardButton("Verify", url=await get_token(client, message.from_user.id, f"https://telegram.me/{username}?start="))
        ],[
            InlineKeyboardButton("How To Open Link & Verify", url=VERIFY_TUTORIAL)
        ]]
        # Add Buy Premium button just below
        btn += buy_premium_keyboard()
        await message.reply_text(
            text="<b>You are not verified !\nKindly verify to continue !</b>",
            protect_content=True,
            reply_markup=InlineKeyboardMarkup(btn)
        )
        return

    try:
        msg = await client.get_messages(LOG_CHANNEL, int(decode_file_id))
        if msg.media:
            media = getattr(msg, msg.media.value)
            title = formate_file_name(media.file_name)
            size = get_size(media.file_size)
            f_caption = f"<code>{title}</code>"

            if CUSTOM_FILE_CAPTION:
                try:
                    f_caption = CUSTOM_FILE_CAPTION.format(
                        file_name='' if title is None else title,
                        file_size='' if size is None else size,
                        file_caption=''
                    )
                except:
                    pass

            reply_markup = None
            if STREAM_MODE == True:
                if msg.video or msg.document:
                    log_msg = msg
                    stream = f"{URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                    download = f"{URL}{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                    button = [[
                        InlineKeyboardButton("• ᴅᴏᴡɴʟᴏᴀᴅ •", url=download),
                        InlineKeyboardButton('• ᴡᴀᴛᴄʜ •', url=stream)
                    ],[
                        InlineKeyboardButton("• ᴡᴀᴛᴄʜ ɪɴ ᴡᴇʙ ᴀᴘᴘ •", web_app=WebAppInfo(url=stream))
                    ]]
                    reply_markup = InlineKeyboardMarkup(button)

            del_msg = await msg.copy(
                chat_id=message.from_user.id,
                caption=f_caption,
                reply_markup=reply_markup,
                protect_content=False
            )
        else:
            del_msg = await msg.copy(chat_id=message.from_user.id, protect_content=False)

        if AUTO_DELETE_MODE == True:
            k = await client.send_message(
                chat_id=message.from_user.id,
                text=f"<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\nThis Movie File/Video will be deleted in <b><u>{AUTO_DELETE} minutes</u> 🫥 <i></b>(Due to Copyright Issues)</i>.\n\n<b><i>Please forward this File/Video to your Saved Messages and Start Download there</b>"
            )
            await asyncio.sleep(AUTO_DELETE_TIME)
            try:
                await del_msg.delete()
            except:
                pass
            await k.edit_text("<b>Your File/Video is successfully deleted!!!</b>")
        return
    except Exception as e:
        logger.exception(e)
        return
    # ---------------------------------------------------------

# ==========================
# Shortener / API commands
# ==========================
@Client.on_message(filters.command('api') & filters.private)
async def shortener_api_handler(client, m: Message):
    # FSub
    ok, kb = await check_force_subscribe(client, m.from_user.id)
    if not ok:
        return await m.reply_text(FSUB_TEXT, reply_markup=kb, disable_web_page_preview=True)

    user_id = m.from_user.id
    user = await get_user(user_id)
    cmd = m.command

    if len(cmd) == 1:
        s = script.SHORTENER_API_MESSAGE.format(base_site=user.get("base_site"), shortener_api=user.get("shortener_api"))
        return await m.reply(s)

    elif len(cmd) == 2:
        api = cmd[1].strip()
        await update_user_info(user_id, {"shortener_api": api})
        await m.reply("<b>Shortener API updated successfully to</b> " + api)

@Client.on_message(filters.command("base_site") & filters.private)
async def base_site_handler(client, m: Message):
    # FSub
    ok, kb = await check_force_subscribe(client, m.from_user.id)
    if not ok:
        return await m.reply_text(FSUB_TEXT, reply_markup=kb, disable_web_page_preview=True)

    user_id = m.from_user.id
    user = await get_user(user_id)
    cmd = m.command
    text = f"`/base_site (base_site)`\n\n<b>Current base site: {user.get('base_site', 'None')}\n\n EX:</b> `/base_site shortnerdomain.com`\n\nIf You Want To Remove Base Site Then Copy This And Send To Bot - `/base_site None`"
    if len(cmd) == 1:
        return await m.reply(text=text, disable_web_page_preview=True)
    elif len(cmd) == 2:
        base_site = cmd[1].strip()
        if base_site == "None":
            await update_user_info(user_id, {"base_site": None})
            return await m.reply("<b>Base Site removed successfully</b>")
        if not domain(base_site):
            return await m.reply(text=text, disable_web_page_preview=True)
        await update_user_info(user_id, {"base_site": base_site})
        await m.reply("<b>Base Site updated successfully</b>")

# ==========================
# Premium Admin Commands
# ==========================
@Client.on_message(filters.private & filters.command("add_premium") & filters.user(ADMINS))
async def add_premium_cmd(client, message: Message):
    """
    /add_premium user_id days
    """
    try:
        user_id = int(message.command[1])
        days = int(message.command[2])
    except Exception:
        return await message.reply_text("Usage: <code>/add_premium user_id days</code>")

    await set_premium(user_id, days)
    exp_ts = _now_ts() + days * 86400
    exp_dt = datetime.utcfromtimestamp(exp_ts).strftime("%Y-%m-%d %H:%M:%S UTC")
    await message.reply_text(f"✅ Premium added for <code>{user_id}</code> for <b>{days}</b> days.\nExpire: <b>{exp_dt}</b>")

@Client.on_message(filters.private & filters.command("remove_premium") & filters.user(ADMINS))
async def remove_premium_cmd(client, message: Message):
    """
    /remove_premium user_id
    """
    try:
        user_id = int(message.command[1])
    except Exception:
        return await message.reply_text("Usage: <code>/remove_premium user_id</code>")

    await remove_premium(user_id)
    await message.reply_text(f"❌ Premium removed for <code>{user_id}</code>")

# ==========================
# Callbacks (about/help/start/clone + premium)
# ==========================
@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    # FSub refresh
    if query.data == "refresh_fsub":
        ok, kb = await check_force_subscribe(client, query.from_user.id)
        if ok:
            try:
                await query.message.edit_text("✅ You’re all set! Ab aap bot use kar sakte ho.")
            except Exception:
                await query.answer("✅ Joined verified!", show_alert=True)
        else:
            try:
                await query.message.edit_text(FSUB_TEXT, reply_markup=kb, disable_web_page_preview=True)
            except Exception:
                await query.answer("⚠️ Please join all required channels.", show_alert=True)
        return

    # Buy Premium (show payment screen)
    if query.data == "buy_premium":
        # Agar image dena ho to reply_photo use karo (edit_text media change karna harder hota)
        caption = (
            f"💎 <b>Premium Membership Plans</b>\n\n"
            f"{PREMIUM_PLANS_TEXT}\n\n"
            f"📌 <b>Payment Instructions:</b>\n{PREMIUM_PAYMENT_TEXT}\n\n"
            f"🖼️ <b>Scan this QR to Pay</b>\n"
        )
        try:
            await query.message.reply_photo(
                photo=PREMIUM_UPI_QR,
                caption=caption,
                reply_markup=premium_payment_keyboard()
            )
            await query.answer("Premium details sent below.", show_alert=False)
        except Exception:
            # fallback: text only
            await query.message.reply_text(
                caption + f"[QR Link]({PREMIUM_UPI_QR})",
                reply_markup=premium_payment_keyboard(),
                disable_web_page_preview=False
            )
        return

    if query.data == "close_data":
        try:
            await query.message.delete()
        except:
            pass
        return

    elif query.data == "about":
        buttons = [[
            InlineKeyboardButton('Hᴏᴍᴇ', callback_data='start'),
            InlineKeyboardButton('🔒 Cʟᴏsᴇ', callback_data='close_data')
        ]]
        await client.edit_message_media(
            query.message.chat.id,
            query.message.id,
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        me2 = (await client.get_me()).mention
        await query.message.edit_text(
            text=script.ABOUT_TXT.format(me2),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )

    elif query.data == "start":
        # FSub check
        ok, kb = await check_force_subscribe(client, query.from_user.id)
        if not ok:
            try:
                return await query.message.edit_text(FSUB_TEXT, reply_markup=kb, disable_web_page_preview=True)
            except Exception:
                return await query.answer("⚠️ Join required channels first.", show_alert=True)

        buttons = [[
            InlineKeyboardButton('💝 sᴜʙsᴄʀɪʙᴇ ᴍʏ ʏᴏᴜᴛᴜʙᴇ ᴄʜᴀɴɴᴇʟ', url='https://youtube.com/@Tech_VJ')
        ],[
            InlineKeyboardButton('🔍 sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url='https://t.me/vj_bot_disscussion'),
            InlineKeyboardButton('🤖 ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ', url='https://t.me/vj_botz')
        ],[
            InlineKeyboardButton('💁‍♀️ ʜᴇʟᴘ', callback_data='help'),
            InlineKeyboardButton('😊 ᴀʙᴏᴜᴛ', callback_data='about')
        ]]
        buttons += buy_premium_keyboard()
        if CLONE_MODE == True:
            buttons.append([InlineKeyboardButton('🤖 ᴄʀᴇᴀᴛᴇ ʏᴏᴜʀ ᴏᴡɴ ᴄʟᴏɴᴇ ʙᴏᴛ', callback_data='clone')])

        await client.edit_message_media(
            query.message.chat.id,
            query.message.id,
            InputMediaPhoto(random.choice(PICS))
        )
        me2 = (await client.get_me()).mention
        prem = await is_premium(query.from_user.id)
        text = script.START_TXT.format(query.from_user.mention, me2)
        text += f"\n\nStatus: <b>{premium_badge(prem)}</b>"
        await query.message.edit_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML
        )

    elif query.data == "clone":
        buttons = [[
            InlineKeyboardButton('Hᴏᴍᴇ', callback_data='start'),
            InlineKeyboardButton('🔒 Cʟᴏsᴇ', callback_data='close_data')
        ]]
        await client.edit_message_media(
            query.message.chat.id,
            query.message.id,
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.CLONE_TXT.format(query.from_user.mention),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )

    elif query.data == "help":
        # FSub check
        ok, kb = await check_force_subscribe(client, query.from_user.id)
        if not ok:
            try:
                return await query.message.edit_text(FSUB_TEXT, reply_markup=kb, disable_web_page_preview=True)
            except Exception:
                return await query.answer("⚠️ Join required channels first.", show_alert=True)

        buttons = [[
            InlineKeyboardButton('Hᴏᴍᴇ', callback_data='start'),
            InlineKeyboardButton('🔒 Cʟᴏsᴇ', callback_data='close_data')
        ]]
        await client.edit_message_media(
            query.message.chat.id,
            query.message.id,
            InputMediaPhoto(random.choice(PICS))
        )
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.HELP_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
