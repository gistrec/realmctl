import os

from datetime import datetime, timezone, timedelta
from typing import List

from telegram import Bot
from telegram.error import BadRequest

from db import get_setting, set_setting


# === CONFIG ===
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = -1003410760885

MESSAGE_ID_KEY = "realm_status_message_id"

MSK = timezone(timedelta(hours=3))


def _format_message(players: List[str]) -> str:
    now = datetime.now(MSK).strftime("%H:%M")

    if players:
        players_block = "\n".join(f"• {p}" for p in players)
        online = len(players)
    else:
        players_block = "— никого нет —"
        online = 0

    return (
        f"👥 *Онлайн:* {online}\n"
        f"\n"
        f"🟢 *Игроки:*\n"
        f"{players_block}\n"
        f"\n"
        f"🕒 _Обновлено: {now} (МСК)_"
    )


async def update_status(players: List[str]) -> None:
    bot = Bot(token=BOT_TOKEN)
    text = _format_message(players)

    message_id = get_setting(MESSAGE_ID_KEY)

    try:
        if message_id:
            # Пытаемся отредактировать сообщение
            await bot.edit_message_text(
                chat_id=CHAT_ID,
                message_id=int(message_id),
                text=text,
                parse_mode="Markdown",
            )
        else:
            raise ValueError("No message_id")

    except BadRequest as e:
        if "message is too old" in str(e) or "can't be edited" in str(e):
            # Если сообщение старое или его нет — отправляем новое
            msg = await bot.send_message(
                chat_id=CHAT_ID,
                text=text,
                parse_mode="Markdown",
                disable_notification=True,
            )

            # Закрепляем без звука
            await bot.pin_chat_message(
                chat_id=CHAT_ID,
                message_id=msg.message_id,
                disable_notification=True,
            )

            set_setting(MESSAGE_ID_KEY, str(msg.message_id))
