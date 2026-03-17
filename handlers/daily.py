"""
Günlük takip — sabah planı, buton checklist, erteleme, gün içi aktivite
"""
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import get_conn
from utils.helpers import today_str, now_tz, priority_badge, progress_bar
from config import ACTIVITY_OPTIONS, TZ


# ── Yardımcılar ──────────────────────────────────────────────────────────────

def get_today_tasks(user_id: int) -> list:
    """Bugün için geçerli aktif görevleri getir."""
    date = today_str()
    weekday = now_tz().weekday()  # 0=Pzt

    with get_conn() as con:
        tasks = con.execute("""
            SELECT t.*, dl.id as log_id, dl.done, dl.snooze_until
            FROM tasks t
            LEFT JOIN daily_logs dl
                ON dl.task_id = t.id AND dl.user_id = t.user_id AND dl.date = ?
            WHERE t.user_id = ? AND t.active = 1
        """, (date, user_id)).fetchall()

    result = []
    for t in tasks:
        tt = t["task_type"]
        if tt == "daily":
            result.append(t)
        elif tt == "once":
            result.append(t)
        elif tt == "weekly" and weekday == 0:   # Pazartesi
            result.append(t)
        elif tt == "recurring":
            days = json.loads(t["recur_days"] or "[]")
            if weekday in days:
                result.append(t)
    return result


def ensure_logs(user_id: int, tasks: list):
    date = today_str()
    with get_conn() as con:
        for t in tasks:
            con.execute(
                "INSERT OR IGNORE INTO daily_logs(user_id, task_id, date) VALUES(?,?,?)",
                (user_id, t["id"], date)
            )
        con.commit()


def build_checklist_keyboard(tasks: list) -> InlineKeyboardMarkup:
    buttons = []
    for t in tasks:
        done = t["done"]
        icon = "✅" if done else "⬜"
        label = f"{icon} {t['title']}"
        if t["scheduled_time"]:
            label += f" {t['scheduled_time']}"
        buttons.append([
            InlineKeyboardButton(label, callback_data=f"chk_{t['log_id']}_{0 if done else 1}"),
            InlineKeyboardButton("💤", callback_data=f"snooze_{t['log_id']}"),
        ])
    return InlineKeyboardMarkup(buttons)


def checklist_header(tasks: list, date: str) -> str:
    done  = sum(1 for t in tasks if t["done"])
    total = len(tasks)
    bar   = progress_bar(done, total)
    return (
        f"📅 *Bugünün Planı* — {date}\n"
        f"İlerleme: {bar} ({done}/{total})\n\n"
        "✅ = tamamlandı  💤 = ertele\n"
    )


# ── /bugun ────────────────────────────────────────────────────────────────────

async def cmd_today(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    date = today_str()
    tasks = get_today_tasks(uid)

    if not tasks:
        await update.message.reply_text(
            "📭 Bugün için görev yok.\n/gorev_ekle ile ekle!"
        )
        return

    ensure_logs(uid, tasks)
    tasks = get_today_tasks(uid)   # log_id'li hali

    await update.message.reply_text(
        checklist_header(tasks, date),
        parse_mode="Markdown",
        reply_markup=build_checklist_keyboard(tasks)
    )


# ── Checklist buton callback ──────────────────────────────────────────────────

async def cb_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    parts   = query.data.split("_")
    log_id  = int(parts[1])
    new_val = int(parts[2])

    done_at = now_tz().isoformat() if new_val else None
    with get_conn() as con:
        con.execute(
            "UPDATE daily_logs SET done=?, done_at=? WHERE id=?",
            (new_val, done_at, log_id)
        )
        con.commit()

    # Puan ekle
    if new_val:
        with get_conn() as con:
            task_points = con.execute(
                "SELECT t.points FROM tasks t JOIN daily_logs dl ON dl.task_id=t.id WHERE dl.id=?",
                (log_id,)
            ).fetchone()
        if task_points:
            _add_points(uid, task_points[0])

    tasks = get_today_tasks(uid)
    ensure_logs(uid, tasks)
    tasks = get_today_tasks(uid)

    done  = sum(1 for t in tasks if t["done"])
    total = len(tasks)

    await query.edit_message_text(
        checklist_header(tasks, today_str()),
        parse_mode="Markdown",
        reply_markup=build_checklist_keyboard(tasks)
    )

    # Tüm görevler tamamlandıysa kutla
    if done == total and total > 0:
        await ctx.bot.send_message(
            uid,
            "🎉 *Harika!* Bugünkü tüm görevleri tamamladın!\n⭐ +50 bonus puan!",
            parse_mode="Markdown"
        )
        _add_points(uid, 50)


# ── Erteleme (snooze) ─────────────────────────────────────────────────────────

async def cb_snooze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    log_id = int(query.data.replace("snooze_", ""))

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("10 dk",  callback_data=f"snz_{log_id}_10")],
        [InlineKeyboardButton("30 dk",  callback_data=f"snz_{log_id}_30")],
        [InlineKeyboardButton("1 saat", callback_data=f"snz_{log_id}_60")],
        [InlineKeyboardButton("🔙 Geri", callback_data="snooze_back")],
    ])
    await query.edit_message_text("Ne kadar erteleyelim?", reply_markup=buttons)


async def cb_snooze_set(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts  = query.data.split("_")
    log_id = int(parts[1])
    mins   = int(parts[2])

    until = (now_tz() + timedelta(minutes=mins)).isoformat()
    with get_conn() as con:
        con.execute("UPDATE daily_logs SET snooze_until=? WHERE id=?", (until, log_id))
        con.commit()

    # Job kur: dakika sonra hatırlat
    uid = query.from_user.id
    ctx.job_queue.run_once(
        _snooze_reminder,
        when=mins * 60,
        data={"user_id": uid, "log_id": log_id},
        name=f"snooze_{log_id}"
    )
    await query.edit_message_text(f"💤 {mins} dakika sonra hatırlatacağım!")


async def _snooze_reminder(ctx: ContextTypes.DEFAULT_TYPE):
    d = ctx.job.data
    uid    = d["user_id"]
    log_id = d["log_id"]
    with get_conn() as con:
        row = con.execute(
            "SELECT t.title FROM tasks t JOIN daily_logs dl ON dl.task_id=t.id WHERE dl.id=?",
            (log_id,)
        ).fetchone()
    if row:
        await ctx.bot.send_message(
            uid,
            f"⏰ *{row['title']}* için erteleme süresi doldu!\n/bugun ile kontrol et.",
            parse_mode="Markdown"
        )


# ── Aktivite takibi ───────────────────────────────────────────────────────────

async def cmd_ne_yapiyorsun(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await _ask_activity(update.message.chat_id, ctx)


async def _ask_activity(chat_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"act_{key}")]
        for label, key in ACTIVITY_OPTIONS
    ]
    await ctx.bot.send_message(
        chat_id,
        "🤔 *Şu an ne yapıyorsun?*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_activity(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid      = query.from_user.id
    activity = query.data.replace("act_", "")

    label = next((l for l, k in ACTIVITY_OPTIONS if k == activity), activity)

    with get_conn() as con:
        con.execute(
            "INSERT INTO activity_logs(user_id, activity) VALUES(?,?)",
            (uid, activity)
        )
        con.commit()

    await query.edit_message_text(f"✍️ Kaydedildi: *{label}*", parse_mode="Markdown")


# ── Yardımcı: puan ekle ───────────────────────────────────────────────────────

def _add_points(user_id: int, pts: int):
    with get_conn() as con:
        con.execute("""
            INSERT INTO streaks(user_id, total_points)
            VALUES(?, ?)
            ON CONFLICT(user_id) DO UPDATE SET total_points = total_points + excluded.total_points
        """, (user_id, pts))
        con.commit()
