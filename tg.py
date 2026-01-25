import json
import os

from datetime import datetime, timezone, timedelta
from typing import Dict, List

from telegram import Bot
from telegram.error import BadRequest

from db import get_setting, remove_setting, set_setting


# === CONFIG ===
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MESSAGE_ID_KEY = "realm_status_message_id"
PLAYER_SESSIONS_KEY = "realm_player_sessions"

MSK = timezone(timedelta(hours=3))

def _load_player_sessions() -> Dict[str, int]:
    raw = get_setting(PLAYER_SESSIONS_KEY)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    sessions: Dict[str, int] = {}
    for name, ts in data.items():
        if isinstance(name, str) and isinstance(ts, int):
            sessions[name] = ts
    return sessions


def _save_player_sessions(sessions: Dict[str, int]) -> None:
    if not sessions:
        remove_setting(PLAYER_SESSIONS_KEY)
        return
    set_setting(PLAYER_SESSIONS_KEY, json.dumps(sessions))


def _format_duration(started_at: datetime, now: datetime) -> str:
    total_minutes = int((now - started_at).total_seconds() // 60)
    total_minutes = max(total_minutes, 0)

    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours == 0 and minutes == 0:
        return f"(Играет недавно)"

    if hours == 0:
        return f"(Играет {minutes} мин)"

    return f"(Играет {hours}ч {minutes} мин)"


def _format_message(players: List[str], sessions: Dict[str, int]) -> str:
    now_msk = datetime.now(MSK).strftime("%H:%M")
    now_utc = datetime.now(timezone.utc)

    if players:
        players_block = "\n".join(
            f"• {name} {_format_duration(datetime.fromtimestamp(sessions[name], timezone.utc), now_utc)}"
            for name in players
        )
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
        f"🕒 _Обновлено: {now_msk} (МСК)_"
    )


async def update_status(players: List[str]) -> None:
    bot = Bot(token=BOT_TOKEN)
    now_utc = datetime.now(timezone.utc)
    sessions = _load_player_sessions()
    current_players = set(players)
    if not current_players:
        sessions = {}
    else:
        sessions = {name: ts for name, ts in sessions.items() if name in current_players}
        for name in players:
            sessions.setdefault(name, int(now_utc.timestamp()))
    _save_player_sessions(sessions)
    text = _format_message(players, sessions)

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
