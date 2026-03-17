"""
Zamanlanmış işler:
 - Sabah planı (08:00)
 - Gün sonu raporu (21:00)
 - Rastgele aktivite sorusu
 - Görev zamanı bildirimi
 - Haftalık rapor (Pazar 20:00)
"""
import json
from datetime import time, timedelta
from telegram.ext import ContextTypes
from database import get_conn
from handlers.daily import get_today_tasks, ensure_logs, build_checklist_keyboard, checklist_header, _ask_activity
from handlers.stats import send_weekly_report, update_streak, check_badges
from utils.helpers import today_str, now_tz, priority_badge
from config import TZ, MORNING_HOUR, MORNING_MINUTE, EVENING_HOUR, EVENING_MINUTE, WEEKLY_HOUR, WEEKLY_MINUTE, RANDOM_CHECK_HOURS


def get_all_users():
    with get_conn() as con:
        return [r["user_id"] for r in con.execute("SELECT user_id FROM users").fetchall()]


# ── Sabah planı ───────────────────────────────────────────────────────────────

async def job_morning(ctx: ContextTypes.DEFAULT_TYPE):
    for uid in get_all_users():
        try:
            tasks = get_today_tasks(uid)
            if not tasks:
                continue
            ensure_logs(uid, tasks)
            tasks = get_today_tasks(uid)

            # Bugünün en önemli görevi (yüksek öncelikli)
            high = [t for t in tasks if t["priority"] == "yüksek"]
            top_task = ""
            if high:
                top_task = f"\n⭐ *En önemli görev:* {high[0]['title']}"

            header = (
                f"☀️ *Günaydın!* Bugünün planı hazır.\n"
                f"{top_task}\n\n"
                + checklist_header(tasks, today_str())
            )
            await ctx.bot.send_message(
                uid, header,
                parse_mode="Markdown",
                reply_markup=build_checklist_keyboard(tasks)
            )

            # Saat bazlı görev bildirimleri kur
            await _schedule_task_reminders(uid, tasks, ctx)

        except Exception as e:
            print(f"[morning job] user {uid}: {e}")


async def _schedule_task_reminders(user_id: int, tasks: list, ctx):
    """Her görev için o günkü saat bildirimi kur."""
    now = now_tz()
    for t in tasks:
        if not t["scheduled_time"]:
            continue
        h, m = map(int, t["scheduled_time"].split(":"))
        task_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)

        # Hatırlatma: 10 dk önce
        remind_dt = task_dt - timedelta(minutes=10)
        if remind_dt > now:
            delay = (remind_dt - now).total_seconds()
            ctx.job_queue.run_once(
                _task_reminder,
                when=delay,
                data={"user_id": user_id, "title": t["title"], "time": t["scheduled_time"], "mins_before": 10},
                name=f"remind_{t['id']}_{today_str()}_10"
            )

        # Tam zamanı
        if task_dt > now:
            delay = (task_dt - now).total_seconds()
            ctx.job_queue.run_once(
                _task_due,
                when=delay,
                data={"user_id": user_id, "title": t["title"], "log_id": t["log_id"]},
                name=f"due_{t['id']}_{today_str()}"
            )


async def _task_reminder(ctx: ContextTypes.DEFAULT_TYPE):
    d = ctx.job.data
    await ctx.bot.send_message(
        d["user_id"],
        f"⏰ *{d['title']}* başlamak üzere!\n"
        f"Saat: {d['time']} ({d['mins_before']} dakika kaldı)",
        parse_mode="Markdown"
    )


async def _task_due(ctx: ContextTypes.DEFAULT_TYPE):
    d = ctx.job.data
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Yaptım",     callback_data=f"chk_{d['log_id']}_1"),
        InlineKeyboardButton("💤 Ertele",     callback_data=f"snooze_{d['log_id']}"),
    ]])
    await ctx.bot.send_message(
        d["user_id"],
        f"🔔 *{d['title']}* zamanı geldi!",
        parse_mode="Markdown",
        reply_markup=buttons
    )


# ── Gün sonu raporu ───────────────────────────────────────────────────────────

async def job_evening(ctx: ContextTypes.DEFAULT_TYPE):
    for uid in get_all_users():
        try:
            tasks = get_today_tasks(uid)
            if not tasks:
                continue

            done  = sum(1 for t in tasks if t["done"])
            total = len(tasks)

            await ctx.bot.send_message(
                uid,
                f"🌙 *Gün Sonu Özeti*\n\n"
                f"Bugün {total} görevden *{done}* tanesini tamamladın.\n\n"
                f"Tamamlamadıklarını işaretlemek ister misin?",
                parse_mode="Markdown",
                reply_markup=build_checklist_keyboard(tasks)
            )

            # Streak güncelle
            update_streak(uid)

            # Rozet kontrol
            new_badges = await check_badges(uid, ctx)
            for key in new_badges:
                if key in __import__("config").BADGE_DEFS:
                    emoji, name, desc = __import__("config").BADGE_DEFS[key]
                    await ctx.bot.send_message(
                        uid,
                        f"🏅 *Yeni Rozet Kazandın!*\n{emoji} *{name}*\n_{desc}_",
                        parse_mode="Markdown"
                    )

        except Exception as e:
            print(f"[evening job] user {uid}: {e}")


# ── Rastgele aktivite sorusu ───────────────────────────────────────────────────

async def job_random_check(ctx: ContextTypes.DEFAULT_TYPE):
    if RANDOM_CHECK_HOURS <= 0:
        return
    now = now_tz()
    # Sadece 09:00 - 22:00 arası sor
    if not (9 <= now.hour < 22):
        return
    for uid in get_all_users():
        try:
            await _ask_activity(uid, ctx)
        except Exception as e:
            print(f"[random check] user {uid}: {e}")


# ── Haftalık rapor ────────────────────────────────────────────────────────────

async def job_weekly(ctx: ContextTypes.DEFAULT_TYPE):
    for uid in get_all_users():
        try:
            await send_weekly_report(uid, uid, ctx)
        except Exception as e:
            print(f"[weekly job] user {uid}: {e}")


# ── Scheduler kayıt fonksiyonu ────────────────────────────────────────────────

def register_jobs(app):
    jq = app.job_queue

    jq.run_daily(job_morning,
                 time=time(MORNING_HOUR, MORNING_MINUTE, tzinfo=TZ),
                 name="morning")

    jq.run_daily(job_evening,
                 time=time(EVENING_HOUR, EVENING_MINUTE, tzinfo=TZ),
                 name="evening")

    jq.run_daily(job_weekly,
                 time=time(WEEKLY_HOUR, WEEKLY_MINUTE, tzinfo=TZ),
                 days=(6,),   # Pazar
                 name="weekly")

    if RANDOM_CHECK_HOURS > 0:
        jq.run_repeating(
            job_random_check,
            interval=RANDOM_CHECK_HOURS * 3600,
            first=3600,  # 1 saat sonra ilk çalışma
            name="random_check"
        )
