import json
import os

from datetime import datetime, timezone, timedelta
from typing import Dict, List, TypedDict

from telegram import Bot
from telegram.error import BadRequest

from db import get_setting, remove_setting, set_setting


# === CONFIG ===
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MESSAGE_ID_KEY = "realm_status_message_id"
PLAYER_SESSIONS_KEY = "realm_player_sessions"
TERRARIA_PLAYER_SESSIONS_KEY = "terraria_player_sessions"
SESSION_GRACE_PERIOD = timedelta(minutes=10)

MSK = timezone(timedelta(hours=3))

class PlayerSession(TypedDict):
    started_at: int
    last_seen: int


def _load_player_sessions() -> Dict[str, PlayerSession]:
    raw = get_setting(PLAYER_SESSIONS_KEY)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    sessions: Dict[str, PlayerSession] = {}
    for name, session in data.items():
        if not isinstance(name, str):
            continue
        if isinstance(session, int):
            sessions[name] = {"started_at": session, "last_seen": session}
            continue
        if isinstance(session, dict):
            started_at = session.get("started_at")
            last_seen = session.get("last_seen")
            if isinstance(started_at, int) and isinstance(last_seen, int):
                sessions[name] = {"started_at": started_at, "last_seen": last_seen}
    return sessions


def _save_player_sessions(sessions: Dict[str, PlayerSession]) -> None:
    if not sessions:
        remove_setting(PLAYER_SESSIONS_KEY)
        return
    set_setting(PLAYER_SESSIONS_KEY, json.dumps(sessions))


def _load_terraria_players() -> List[str]:
    raw = get_setting(TERRARIA_PLAYER_SESSIONS_KEY)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    return [name for name in data.keys() if isinstance(name, str)]


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


def _format_message(players: List[str], sessions: Dict[str, PlayerSession]) -> str:
    now_msk = datetime.now(MSK).strftime("%H:%M")
    now_utc = datetime.now(timezone.utc)

    if players:
        players_rows = []
        for name in players:
            if name in sessions:
                duration = _format_duration(datetime.fromtimestamp(sessions[name]["started_at"], timezone.utc), now_utc)
                players_rows.append(f"• {name} {duration}")
            else:
                players_rows.append(f"• {name}")
        players_block = "\n".join(players_rows)
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
    terraria_players = _load_terraria_players()
    now_ts = int(now_utc.timestamp())
    for name in players:
        if name in sessions:
            sessions[name]["last_seen"] = now_ts
        else:
            sessions[name] = {"started_at": now_ts, "last_seen": now_ts}
    cutoff = int((now_utc - SESSION_GRACE_PERIOD).timestamp())
    sessions = {
        name: session
        for name, session in sessions.items()
        if session["last_seen"] >= cutoff
    }
    _save_player_sessions(sessions)

    all_players = players + [name for name in terraria_players if name not in players]
    text = _format_message(all_players, sessions)

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
