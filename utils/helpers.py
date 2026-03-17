"""Yardımcı fonksiyonlar"""
from datetime import datetime, date
from zoneinfo import ZoneInfo
from config import TZ, PRIORITY_EMOJI


def now_tz() -> datetime:
    return datetime.now(TZ)


def today_str() -> str:
    return now_tz().strftime("%Y-%m-%d")


def fmt_time(t: str) -> str:
    """'08:30' → '08:30 ⏰'"""
    return f"{t} ⏰" if t else ""


def priority_badge(p: str) -> str:
    return PRIORITY_EMOJI.get(p, "🟡")


def progress_bar(done: int, total: int, width: int = 10) -> str:
    if total == 0:
        return "░" * width + " 0%"
    pct = done / total
    filled = round(pct * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"`{bar}` {round(pct*100)}%"


def day_name(weekday: int) -> str:
    names = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
    return names[weekday]
