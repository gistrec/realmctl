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
PLAYTIME_LOG_KEY = "realm_playtime_log"

SESSION_GRACE_PERIOD = timedelta(minutes=10)
WEEK_SECONDS = 7 * 24 * 3600

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


# Playtime log: {player: [[start_ts, duration_secs], ...]}
def _load_playtime_log() -> Dict[str, List[List[int]]]:
    raw = get_setting(PLAYTIME_LOG_KEY)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _save_playtime_log(log: Dict[str, List[List[int]]], now_ts: int) -> None:
    cutoff = now_ts - WEEK_SECONDS
    pruned = {
        player: [[s, d] for s, d in entries if s >= cutoff]
        for player, entries in log.items()
    }
    pruned = {p: e for p, e in pruned.items() if e}
    if not pruned:
        remove_setting(PLAYTIME_LOG_KEY)
    else:
        set_setting(PLAYTIME_LOG_KEY, json.dumps(pruned))


def _record_session(log: Dict[str, List[List[int]]], player: str, start_ts: int, end_ts: int) -> None:
    duration = max(end_ts - start_ts, 0)
    if duration == 0:
        return
    log.setdefault(player, []).append([start_ts, duration])


def _format_playtime(total_seconds: int) -> str:
    total_minutes = total_seconds // 60
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours == 0:
        return f"{minutes} мин"
    return f"{hours}ч {minutes} мин"


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


def _format_message(players: List[str], sessions: Dict[str, PlayerSession], playtime_log: Dict[str, List[List[int]]], now_ts: int) -> str:
    now_msk = datetime.now(MSK).strftime("%H:%M")
    now_utc = datetime.fromtimestamp(now_ts, timezone.utc)

    if players:
        players_block = "\n".join(
            f"• {name} {_format_duration(datetime.fromtimestamp(sessions[name]['started_at'], timezone.utc), now_utc)}"
            for name in players
        )
        online = len(players)
    else:
        players_block = "— никого нет —"
        online = 0

    # Weekly stats: all players with playtime in the last 7 days
    cutoff = now_ts - WEEK_SECONDS
    weekly: Dict[str, int] = {}
    for player, entries in playtime_log.items():
        total = sum(d for s, d in entries if s >= cutoff)
        if total > 0:
            weekly[player] = total
    for name, session in sessions.items():
        weekly[name] = weekly.get(name, 0) + max(now_ts - session["started_at"], 0)

    if weekly:
        weekly_lines = "\n".join(
            f"• {name}: {_format_playtime(secs)}"
            for name, secs in sorted(weekly.items(), key=lambda x: -x[1])
        )
        weekly_section = f"\n📊 *За неделю:*\n{weekly_lines}\n"
    else:
        weekly_section = ""

    return (
        f"👥 *Онлайн:* {online}\n"
        f"\n"
        f"🟢 *Игроки:*\n"
        f"{players_block}\n"
        f"{weekly_section}"
        f"\n"
        f"🕒 _Обновлено: {now_msk} (МСК)_"
    )


async def update_status(players: List[str]) -> None:
    bot = Bot(token=BOT_TOKEN)
    now_utc = datetime.now(timezone.utc)
    now_ts = int(now_utc.timestamp())

    sessions = _load_player_sessions()
    playtime_log = _load_playtime_log()

    # Update last_seen for current players, create new sessions for newcomers
    for name in players:
        if name in sessions:
            sessions[name]["last_seen"] = now_ts
        else:
            sessions[name] = {"started_at": now_ts, "last_seen": now_ts}

    # Record completed sessions for players whose grace period has expired
    grace_cutoff = int((now_utc - SESSION_GRACE_PERIOD).timestamp())
    for name, session in sessions.items():
        if session["last_seen"] < grace_cutoff:
            _record_session(playtime_log, name, session["started_at"], session["last_seen"])

    # Prune expired sessions
    sessions = {
        name: session
        for name, session in sessions.items()
        if session["last_seen"] >= grace_cutoff
    }

    _save_player_sessions(sessions)
    _save_playtime_log(playtime_log, now_ts)
    text = _format_message(players, sessions, playtime_log, now_ts)

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
