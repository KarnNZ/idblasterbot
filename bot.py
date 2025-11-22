import logging
import os

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# -------------------------------------------------
# Logging
# -------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_NAME = "IDBlasterBot"
BRAND_TAGLINE = "Powered by MadLabz • $COMMAND"

# 🔗 Tweak these to your real links
MADLABZ_SITE_URL = "https://madlabz.app"
COMMAND_TG_URL = "https://t.me/LaunchCommand"   # TODO: replace
COMMAND_BUY_URL = "https://pump.fun/coin/943mLkNDxGgTEb8hWkGLqhSAqiCs9fGcBCF8vkj8pump"         # TODO: replace


# -------------------------------------------------
# Helpers
# -------------------------------------------------
async def is_user_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    In groups/supergroups: only admins can use ID commands.
    In private chats: always allowed.
    """
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return False

    if chat.type == "private":
        # In DMs with the bot, always allow.
        return True

    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
    except Exception as e:
        logger.warning("Failed to fetch chat member: %s", e)
        return False

    return member.status in ("creator", "administrator")


def build_id_payload(update: Update):
    """
    Build the ID info text and raw values for /id.
    Returns (text, user_id, chat_id, topic_id_or_None).
    """
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    thread_id = msg.message_thread_id if msg else None
    chat_id = chat.id if chat else "(no chat)"
    chat_type = chat.type if chat else "(unknown)"
    chat_title = chat.title if chat and chat.title else "(no title)"

    lines = []
    lines.append("🔎 <b>IDBlasterBot – ID Inspector</b>")
    lines.append("")
    lines.append("📌 <b>Chat Information</b>")
    lines.append(f"Chat ID: <code>{chat_id}</code>")
    lines.append(f"Chat Type: <code>{chat_type}</code>")
    lines.append(f"Chat Title: {chat_title}")
    if thread_id is not None:
        lines.append(f"Topic ID (message_thread_id): <code>{thread_id}</code>")
    else:
        lines.append("Topic ID: <i>(not in a topic)</i>")
    lines.append("")

    user_id = None
    if user:
        user_id = user.id
        username = f"@{user.username}" if user.username else "(no username)"
        lines.append("👤 <b>Your Information</b>")
        lines.append(f"User: {username}")
        lines.append(f"User ID: <code>{user_id}</code>")
        lines.append("")
    else:
        lines.append("👤 <b>Your Information</b>")
        lines.append("(no user info)")
        lines.append("")

    lines.append(f"🔧 <i>{BRAND_TAGLINE}</i>")
    # very light footer – Telegram auto-links this
    lines.append(f"🌐 {MADLABZ_SITE_URL}")

    text = "\n".join(lines)
    return text, user_id, chat_id, thread_id


def build_copy_buttons(user_id, chat_id, topic_id):
    buttons = []

    if user_id is not None:
        buttons.append(
            InlineKeyboardButton(
                "👤 Copy User ID", callback_data=f"copy:user:{user_id}"
            )
        )

    if chat_id is not None:
        buttons.append(
            InlineKeyboardButton(
                "💬 Copy Chat ID", callback_data=f"copy:chat:{chat_id}"
            )
        )

    if topic_id is not None:
        buttons.append(
            InlineKeyboardButton(
                "🧵 Copy Topic ID", callback_data=f"copy:topic:{topic_id}"
            )
        )

    if not buttons:
        return None

    keyboard = InlineKeyboardMarkup([buttons])
    return keyboard


def _reply_in_same_place(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    keyboard: InlineKeyboardMarkup | None = None,
):
    """
    Helper to reply either in the current topic or just to the message,
    so commands don't jump to main chat.
    Returns an awaitable (caller must await).
    """
    msg = update.effective_message
    chat = update.effective_chat
    thread_id = msg.message_thread_id if msg else None

    if chat and thread_id is not None:
        # Force-send into the same topic
        return context.bot.send_message(
            chat_id=chat.id,
            message_thread_id=thread_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
    else:
        # Normal reply (private or non-topic chat)
        return msg.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )


# -------------------------------------------------
# Handlers
# -------------------------------------------------
async def start_or_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    lines = [
        f"👋 Hey {user.mention_html() if user else 'there'}!",
        "",
        f"<b>{BOT_NAME}</b> helps you quickly view:",
        "• Chat ID",
        "• Topic ID",
        "• User ID",
        "",
        "🔧 <b>Commands</b>",
        "• <code>/id</code> – Full IDs + buttons",
        "• <code>/chat</code> – Only chat ID",
        "• <code>/topic</code> – Only topic ID",
        "• <code>/replyid</code> – ID of the user you reply to",
        "• <code>/about</code> – About MadLabz & $COMMAND",
        "• <code>/help</code> – Show this help message",
        "",
        "<b>Permissions</b>",
        "• In groups, ID commands are <i>admin-only</i>.",
        "• In private chat with the bot, everyone can use them.",
        "",
        f"⚙️ <i>{BRAND_TAGLINE}</i>",
        f"🌐 {MADLABZ_SITE_URL}",
    ]

    await _reply_in_same_place(update, context, "\n".join(lines))


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Brand story + shill zone for MadLabz / $COMMAND, but opt-in."""
    text = (
        "⚙️ <b>About IDBlasterBot</b>\n\n"
        "<b>IDBlasterBot</b> is a tiny utility built for founders, mods, and devs who "
        "need chat IDs, topic IDs, and user IDs <i>fast</i>.\n\n"
        "It’s part of the <b>MadLabz</b> ecosystem — the lab behind tools like:\n"
        "• SubutAI (AI warlord assistant)\n"
        "\n"   # <<— added whitespace line
        "<b>$COMMAND</b> is the core token that powers the MadLabz empire.\n\n"
        f"🌐 MadLabz Hub: <a href=\"{MADLABZ_SITE_URL}\">{MADLABZ_SITE_URL}</a>\n"
        f"💬 Telegram: <a href=\"{COMMAND_TG_URL}\">{COMMAND_TG_URL}</a>\n"
        f"💰 Buy $COMMAND: <a href=\"{COMMAND_BUY_URL}\">Trade link</a>\n\n"
        f"⚙️ <i>{BRAND_TAGLINE}</i>"
    )

    await _reply_in_same_place(update, context, text)


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main ID inspector with copy buttons, no sticky."""
    if not await is_user_admin(update, context):
        await _reply_in_same_place(
            update,
            context,
            "⛔ Only chat admins can use /id in groups.\n"
            "Use it in a private chat with the bot if you’re not an admin.",
        )
        return

    text, user_id, chat_id, topic_id = build_id_payload(update)
    keyboard = build_copy_buttons(user_id, chat_id, topic_id)

    await _reply_in_same_place(update, context, text, keyboard)


async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show only chat ID (admin-only in groups)."""
    if not await is_user_admin(update, context):
        await _reply_in_same_place(
            update,
            context,
            "⛔ Only chat admins can use /chat in groups.",
        )
        return

    chat = update.effective_chat
    if not chat:
        return

    chat_id = chat.id
    chat_type = chat.type
    chat_title = chat.title if chat.title else "(no title)"

    text = (
        "💬 <b>Chat ID</b>\n"
        f"Chat ID: <code>{chat_id}</code>\n"
        f"Chat Type: <code>{chat_type}</code>\n"
        f"Chat Title: {chat_title}\n\n"
        f"🔧 <i>{BRAND_TAGLINE}</i>\n"
        f"🌐 {MADLABZ_SITE_URL}"
    )

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("💬 Copy Chat ID", callback_data=f"copy:chat:{chat_id}")]]
    )

    await _reply_in_same_place(update, context, text, keyboard)


async def topic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show only topic ID (admin-only in groups)."""
    if not await is_user_admin(update, context):
        await _reply_in_same_place(
            update,
            context,
            "⛔ Only chat admins can use /topic in groups.",
        )
        return

    msg = update.effective_message
    if not msg:
        return

    thread_id = msg.message_thread_id
    if thread_id is None:
        text = (
            "🧵 <b>Topic ID</b>\n"
            "Topic ID: <i>None (not in a topic)</i>\n\n"
            f"🔧 <i>{BRAND_TAGLINE}</i>\n"
            f"🌐 {MADLABZ_SITE_URL}"
        )
        await _reply_in_same_place(update, context, text)
        return

    text = (
        "🧵 <b>Topic ID</b>\n"
        f"Topic ID (message_thread_id): <code>{thread_id}</code>\n\n"
        f"🔧 <i>{BRAND_TAGLINE}</i>\n"
        f"🌐 {MADLABZ_SITE_URL}"
    )

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🧵 Copy Topic ID", callback_data=f"copy:topic:{thread_id}")]]
    )

    await _reply_in_same_place(update, context, text, keyboard)


async def replyid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Show ID of the user you replied to (admin-only in groups).
    """
    if not await is_user_admin(update, context):
        await _reply_in_same_place(
            update,
            context,
            "⛔ Only chat admins can use /replyid in groups.",
        )
        return

    msg = update.effective_message
    if not msg:
        return

    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        await _reply_in_same_place(
            update,
            context,
            "ℹ️ Reply to a user's message, then send /replyid to see their ID.",
        )
        return

    target = msg.reply_to_message.from_user
    username = f"@{target.username}" if target.username else "(no username)"

    text = (
        "🎯 <b>Replied User</b>\n"
        f"User: {username}\n"
        f"User ID: <code>{target.id}</code>\n\n"
        f"🔧 <i>{BRAND_TAGLINE}</i>\n"
        f"🌐 {MADLABZ_SITE_URL}"
    )

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("👤 Copy User ID", callback_data=f"copy:user:{target.id}")]]
    )

    await _reply_in_same_place(update, context, text, keyboard)


async def copy_id_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle inline 'Copy ID' buttons.
    FIXED: just reply to the button message itself, so it works
    in main chat and topics without any thread errors.
    """
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    if not data.startswith("copy:"):
        return

    try:
        _, id_type, value = data.split(":", 2)
    except ValueError:
        return

    label_map = {
        "user": "User ID",
        "chat": "Chat ID",
        "topic": "Topic ID",
    }
    label = label_map.get(id_type, "ID")

    text = f"{label}: <code>{value}</code>"

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# Optional: raw debug handler (commented out by default)
async def debug_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """If enabled, dumps IDs for every message (for development)."""
    msg = update.effective_message
    if not msg:
        return

    chat = update.effective_chat
    user = update.effective_user

    chat_id = chat.id if chat else "(no chat)"
    thread_id = msg.message_thread_id
    user_id = user.id if user else "(no user)"

    text = (
        "🧪 <b>Debug IDs</b>\n"
        f"Chat ID: <code>{chat_id}</code>\n"
        f"Topic ID: <code>{thread_id}</code>\n"
        f"User ID: <code>{user_id}</code>"
    )

    await _reply_in_same_place(update, context, text)


# -------------------------------------------------
# Main
# -------------------------------------------------
def main() -> None:
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("BOT_TOKEN missing in environment")

    application = Application.builder().token(bot_token).build()

    # Commands
    application.add_handler(CommandHandler("start", start_or_help))
    application.add_handler(CommandHandler("help", start_or_help))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("chat", chat_command))
    application.add_handler(CommandHandler("topic", topic_command))
    application.add_handler(CommandHandler("replyid", replyid_command))

    # Copy ID buttons
    application.add_handler(CallbackQueryHandler(copy_id_callback, pattern=r"^copy:"))

    # Optional: uncomment for full debug mode
    # application.add_handler(MessageHandler(filters.ALL, debug_all))

    logger.info("Starting IDBlasterBot...")
    application.run_polling()


if __name__ == "__main__":
    main()
