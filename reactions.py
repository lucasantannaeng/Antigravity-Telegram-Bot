"""
Telegram Emoji Reactions Helper
Provides interactive status reactions on user messages (e.g. thinking, working, success, error).
"""

import logging
from telegram import ReactionTypeEmoji
from telegram.ext import ContextTypes

logger = logging.getLogger("AntigravityReactions")


async def set_message_reaction(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, emoji: str):
    """Sets an emoji reaction on a message (best-effort)."""
    try:
        await context.bot.set_message_reaction(
            chat_id=chat_id,
            message_id=message_id,
            reaction=[ReactionTypeEmoji(emoji)]
        )
    except Exception as e:
        logger.debug(f"Reaction '{emoji}' could not be set: {e}")
