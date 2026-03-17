"""
Görev yönetimi — ekle, sil, düzenle, listele
ConversationHandler tabanlı çok adımlı akış
"""
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)
from database import get_conn
from utils.helpers import today_str, priority_badge, fmt_time
from config import PRIORITY_EMOJI, TYPE_LABEL

# ── Conversation states ──────────────────────────────────────────────────────
(
    ASK_TITLE, ASK_TYPE, ASK_CATEGORY, ASK_PRIORITY,
    ASK_TIME, ASK_DURATION, ASK_NOTE, ASK_RECUR_DAYS,
    EDIT_PICK, EDIT_FIELD, EDIT_VALUE,
) = range(11)

# ── Yardımcı ────────────────────────────────────────────────────────────────

def get_categories(user_id: int) -> list:
    with get_conn() as con:
        return con.execute(
            "SELECT id, name, emoji FROM categories WHERE user_id=? ORDER BY name",
            (user_id,)
        ).fetchall()


def get_tasks(user_id: int, only_active=True) -> list:
    q = "SELECT * FROM tasks WHERE user_id=?"
    if only_active:
        q += " AND active=1"
    q += " ORDER BY scheduled_time, id"
    with get_conn() as con:
        return con.execute(q, (user_id,)).fetchall()


def task_line(t) -> str:
    pb = priority_badge(t["priority"])
    time_str = f" {fmt_time(t['scheduled_time'])}" if t["scheduled_time"] else ""
    note_str = f"\n    📝 {t['note']}" if t["note"] else ""
    return f"{pb} *{t['title']}*{time_str}{note_str}"


def cancel_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ İptal", callback_data="cancel")]])


# ── /gorev_ekle ──────────────────────────────────────────────────────────────

async def cmd_add_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text(
        "➕ *Yeni Görev Ekle*\n\nGörevin adı nedir?",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard()
    )
    return ASK_TITLE


async def got_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["title"] = update.message.text.strip()
    buttons = [
        [InlineKeyboardButton("📅 Günlük",        callback_data="type_daily")],
        [InlineKeyboardButton("📆 Haftalık",       callback_data="type_weekly")],
        [InlineKeyboardButton("🔁 Tekrarlayan",    callback_data="type_recurring")],
        [InlineKeyboardButton("1️⃣ Tek Seferlik",   callback_data="type_once")],
    ]
    await update.message.reply_text(
        "Görev türü nedir?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return ASK_TYPE


async def got_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_type = query.data.replace("type_", "")
    ctx.user_data["task_type"] = task_type

    if task_type == "recurring":
        days_buttons = [
            [
                InlineKeyboardButton("Pzt", callback_data="day_0"),
                InlineKeyboardButton("Sal", callback_data="day_1"),
                InlineKeyboardButton("Çar", callback_data="day_2"),
                InlineKeyboardButton("Per", callback_data="day_3"),
            ],
            [
                InlineKeyboardButton("Cum", callback_data="day_4"),
                InlineKeyboardButton("Cmt", callback_data="day_5"),
                InlineKeyboardButton("Paz", callback_data="day_6"),
            ],
            [InlineKeyboardButton("✅ Tamam", callback_data="days_done")],
        ]
        ctx.user_data["recur_days"] = []
        await query.edit_message_text(
            "Hangi günler tekrarlansın? (Birden fazla seçebilirsin)",
            reply_markup=InlineKeyboardMarkup(days_buttons)
        )
        return ASK_RECUR_DAYS

    return await ask_category(query, ctx)


async def got_recur_day(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "days_done":
        return await ask_category(query, ctx)
    day = int(query.data.replace("day_", ""))
    days = ctx.user_data.setdefault("recur_days", [])
    if day in days:
        days.remove(day)
    else:
        days.append(day)
    day_names = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
    selected = " ".join(day_names[d] for d in sorted(days)) or "Henüz seçilmedi"
    days_buttons = [
        [
            InlineKeyboardButton("Pzt", callback_data="day_0"),
            InlineKeyboardButton("Sal", callback_data="day_1"),
            InlineKeyboardButton("Çar", callback_data="day_2"),
            InlineKeyboardButton("Per", callback_data="day_3"),
        ],
        [
            InlineKeyboardButton("Cum", callback_data="day_4"),
            InlineKeyboardButton("Cmt", callback_data="day_5"),
            InlineKeyboardButton("Paz", callback_data="day_6"),
        ],
        [InlineKeyboardButton("✅ Tamam", callback_data="days_done")],
    ]
    await query.edit_message_text(
        f"Seçilen günler: *{selected}*\nDevam etmek için ✅ Tamam'a bas.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(days_buttons)
    )
    return ASK_RECUR_DAYS


async def ask_category(query_or_msg, ctx: ContextTypes.DEFAULT_TYPE):
    uid = query_or_msg.from_user.id
    cats = get_categories(uid)
    buttons = [[InlineKeyboardButton(f"{c['emoji']} {c['name']}", callback_data=f"cat_{c['id']}")] for c in cats]
    buttons.append([InlineKeyboardButton("➕ Kategorisiz", callback_data="cat_0")])
    text = "Hangi kategoriye ait?"
    if hasattr(query_or_msg, "edit_message_text"):
        await query_or_msg.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await query_or_msg.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    return ASK_CATEGORY


async def got_category(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.replace("cat_", ""))
    ctx.user_data["category_id"] = cat_id if cat_id else None

    buttons = [
        [InlineKeyboardButton("🔴 Yüksek", callback_data="pri_yüksek")],
        [InlineKeyboardButton("🟡 Orta",   callback_data="pri_orta")],
        [InlineKeyboardButton("🟢 Düşük",  callback_data="pri_düşük")],
    ]
    await query.edit_message_text("Önceliği nedir?", reply_markup=InlineKeyboardMarkup(buttons))
    return ASK_PRIORITY


async def got_priority(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["priority"] = query.data.replace("pri_", "")

    await query.edit_message_text(
        "Görev saati? (örn: `08:30`)\n_Saat yoksa 'yok' yaz._",
        parse_mode="Markdown"
    )
    return ASK_TIME


async def got_time(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() in ("yok", "-", ""):
        ctx.user_data["scheduled_time"] = None
    else:
        # basit doğrulama
        try:
            h, m = text.split(":")
            assert 0 <= int(h) <= 23 and 0 <= int(m) <= 59
            ctx.user_data["scheduled_time"] = f"{int(h):02d}:{int(m):02d}"
        except Exception:
            await update.message.reply_text("⚠️ Geçersiz format. Örn: `08:30` ya da 'yok'", parse_mode="Markdown")
            return ASK_TIME

    await update.message.reply_text(
        "Tahmini süre? (dakika, örn: `30`)\n_Yoksa 'yok' yaz._",
        parse_mode="Markdown"
    )
    return ASK_DURATION


async def got_duration(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        ctx.user_data["duration_min"] = int(text) if text.lower() not in ("yok", "-") else 0
    except ValueError:
        ctx.user_data["duration_min"] = 0

    await update.message.reply_text(
        "Göreve not eklemek ister misin? _('yok' yaz geçmek için)_",
        parse_mode="Markdown"
    )
    return ASK_NOTE


async def got_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    ctx.user_data["note"] = None if text.lower() in ("yok", "-") else text
    await _save_task(update, ctx)
    return ConversationHandler.END


async def _save_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    d = ctx.user_data
    recur = json.dumps(d.get("recur_days", [])) if d.get("task_type") == "recurring" else None

    with get_conn() as con:
        con.execute("""
            INSERT INTO tasks(user_id, title, note, category_id, priority,
                              task_type, recur_days, scheduled_time, duration_min)
            VALUES(?,?,?,?,?,?,?,?,?)
        """, (
            uid, d["title"], d.get("note"), d.get("category_id"),
            d.get("priority", "orta"), d.get("task_type", "daily"),
            recur, d.get("scheduled_time"), d.get("duration_min", 0)
        ))

    pb = priority_badge(d.get("priority", "orta"))
    time_str = f"\n⏰ {d['scheduled_time']}" if d.get("scheduled_time") else ""
    dur_str = f"\n⏱ {d['duration_min']} dakika" if d.get("duration_min") else ""
    await update.message.reply_text(
        f"✅ *{d['title']}* eklendi!\n"
        f"{pb} {TYPE_LABEL.get(d.get('task_type','daily'), '')}{time_str}{dur_str}",
        parse_mode="Markdown"
    )


# ── /gorev_sil ───────────────────────────────────────────────────────────────

async def cmd_delete_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    tasks = get_tasks(uid)
    if not tasks:
        await update.message.reply_text("📭 Silinecek görev yok.")
        return
    buttons = [
        [InlineKeyboardButton(f"🗑 {t['title']}", callback_data=f"deltask_{t['id']}")]
        for t in tasks
    ]
    await update.message.reply_text(
        "Hangi görevi silmek istiyorsun?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_delete_task(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    task_id = int(query.data.replace("deltask_", ""))
    with get_conn() as con:
        row = con.execute("SELECT title FROM tasks WHERE id=?", (task_id,)).fetchone()
        con.execute("UPDATE tasks SET active=0 WHERE id=?", (task_id,))
    name = row["title"] if row else "Görev"
    await query.edit_message_text(f"🗑 *{name}* silindi.", parse_mode="Markdown")


# ── /gorevler ─────────────────────────────────────────────────────────────────

async def cmd_list_tasks(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    tasks = get_tasks(uid)
    if not tasks:
        await update.message.reply_text("📭 Henüz görev yok. /gorev_ekle ile başla!")
        return

    # Kategoriye göre grupla
    groups: dict = {}
    with get_conn() as con:
        cats = {r["id"]: f"{r['emoji']} {r['name']}" for r in
                con.execute("SELECT id, name, emoji FROM categories WHERE user_id=?", (uid,)).fetchall()}
    for t in tasks:
        cat = cats.get(t["category_id"], "📌 Genel")
        groups.setdefault(cat, []).append(t)

    lines = [f"📋 *Görevlerin* ({len(tasks)} adet)\n"]
    for cat, ts in groups.items():
        lines.append(f"\n*{cat}*")
        for t in ts:
            lines.append(task_line(t))

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /kategori_ekle ────────────────────────────────────────────────────────────

async def cmd_add_category(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    # /kategori_ekle 🏃 Spor
    if not args:
        await update.message.reply_text(
            "Kullanım: `/kategori_ekle 🏃 Spor`",
            parse_mode="Markdown"
        )
        return
    emoji = args[0] if len(args[0]) <= 2 else "📌"
    name  = " ".join(args[1:]) if len(args) > 1 else " ".join(args)
    uid = update.effective_user.id
    with get_conn() as con:
        con.execute("INSERT INTO categories(user_id, name, emoji) VALUES(?,?,?)", (uid, name, emoji))
    await update.message.reply_text(f"✅ Kategori eklendi: {emoji} *{name}*", parse_mode="Markdown")


# ── ConversationHandler builder ───────────────────────────────────────────────

def build_add_task_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("gorev_ekle", cmd_add_task)],
        states={
            ASK_TITLE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, got_title)],
            ASK_TYPE:      [CallbackQueryHandler(got_type, pattern="^type_")],
            ASK_RECUR_DAYS:[CallbackQueryHandler(got_recur_day, pattern="^(day_|days_done)")],
            ASK_CATEGORY:  [CallbackQueryHandler(got_category, pattern="^cat_")],
            ASK_PRIORITY:  [CallbackQueryHandler(got_priority, pattern="^pri_")],
            ASK_TIME:      [MessageHandler(filters.TEXT & ~filters.COMMAND, got_time)],
            ASK_DURATION:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_duration)],
            ASK_NOTE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, got_note)],
        },
        fallbacks=[
            CallbackQueryHandler(lambda u, c: ConversationHandler.END, pattern="^cancel$"),
            CommandHandler("iptal", lambda u, c: ConversationHandler.END),
        ],
        allow_reentry=True,
    )
