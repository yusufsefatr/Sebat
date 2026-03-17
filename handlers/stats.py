"""
İstatistik, Streak, Rozet, Seviye & Detaylı Analiz
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_conn
from utils.helpers import today_str, now_tz, progress_bar, day_name
from config import BADGE_DEFS


# ════════════════════════════════════════════════════════════════
#  STREAK
# ════════════════════════════════════════════════════════════════

def update_streak(user_id: int):
    date = today_str()
    with get_conn() as con:
        total = con.execute(
            "SELECT COUNT(*) FROM daily_logs WHERE user_id=? AND date=?",
            (user_id, date)
        ).fetchone()[0]
        done = con.execute(
            "SELECT COUNT(*) FROM daily_logs WHERE user_id=? AND date=? AND done=1",
            (user_id, date)
        ).fetchone()[0]

        if total == 0:
            return

        success = (done / total) >= 0.5

        row = con.execute("SELECT * FROM streaks WHERE user_id=?", (user_id,)).fetchone()
        if row is None:
            con.execute(
                "INSERT INTO streaks(user_id, current_streak, best_streak, last_active) VALUES(?,?,?,?)",
                (user_id, 1 if success else 0, 1 if success else 0, date)
            )
        else:
            cur  = row["current_streak"]
            best = row["best_streak"]
            if success:
                cur  += 1
                best  = max(best, cur)
            else:
                cur = 0
            con.execute(
                "UPDATE streaks SET current_streak=?, best_streak=?, last_active=? WHERE user_id=?",
                (cur, best, date, user_id)
            )
        con.commit()


# ════════════════════════════════════════════════════════════════
#  SEVIYE SISTEMI
# ════════════════════════════════════════════════════════════════

LEVELS = [
    (0,    "Başlangıç 🌱"),
    (100,  "Acemi 🔰"),
    (300,  "Gelişen ⚡"),
    (600,  "Kararlı 🔥"),
    (1000, "Usta 💎"),
    (1500, "Şampiyon 👑"),
    (2500, "Efsane 🚀"),
]

def get_level(points: int):
    label = LEVELS[0][1]
    next_thresh = LEVELS[1][0] if len(LEVELS) > 1 else 9999
    for i, (thresh, name) in enumerate(LEVELS):
        if points >= thresh:
            label = name
            next_thresh = LEVELS[i + 1][0] if i + 1 < len(LEVELS) else points + 1
    remaining = max(0, next_thresh - points)
    return label, remaining, next_thresh


# ════════════════════════════════════════════════════════════════
#  ROZET SISTEMI
# ════════════════════════════════════════════════════════════════

async def check_badges(user_id: int, ctx) -> list:
    earned = []
    with get_conn() as con:
        streak = con.execute("SELECT * FROM streaks WHERE user_id=?", (user_id,)).fetchone()
        total_done = con.execute(
            "SELECT COUNT(*) FROM daily_logs WHERE user_id=? AND done=1", (user_id,)
        ).fetchone()[0]

        date = today_str()
        day_total = con.execute(
            "SELECT COUNT(*) FROM daily_logs WHERE user_id=? AND date=?", (user_id, date)
        ).fetchone()[0]
        day_done = con.execute(
            "SELECT COUNT(*) FROM daily_logs WHERE user_id=? AND date=? AND done=1", (user_id, date)
        ).fetchone()[0]
        perfect_day = day_total > 0 and day_total == day_done

        early = con.execute(
            "SELECT COUNT(*) FROM daily_logs WHERE user_id=? AND done=1 AND strftime('%H', done_at) < '07'",
            (user_id,)
        ).fetchone()[0]

        week_done = con.execute(
            "SELECT COUNT(*) FROM daily_logs WHERE user_id=? AND done=1 AND date >= date('now','-7 days','localtime')",
            (user_id,)
        ).fetchone()[0]

        def give(key):
            try:
                con.execute("INSERT INTO badges(user_id, badge_key) VALUES(?,?)", (user_id, key))
                con.commit()
                return True
            except Exception:
                return False

        checks = [
            ("first_task",  total_done >= 1),
            ("streak_3",    streak and streak["current_streak"] >= 3),
            ("streak_7",    streak and streak["current_streak"] >= 7),
            ("streak_30",   streak and streak["current_streak"] >= 30),
            ("perfect_day", perfect_day),
            ("early_bird",  early >= 1),
            ("century",     total_done >= 100),
            ("productive",  week_done >= 50),
        ]
        for key, cond in checks:
            if cond and give(key):
                earned.append(key)

    return earned


# ════════════════════════════════════════════════════════════════
#  /streak
# ════════════════════════════════════════════════════════════════

async def cmd_streak(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    with get_conn() as con:
        row    = con.execute("SELECT * FROM streaks WHERE user_id=?", (uid,)).fetchone()
        badges = con.execute(
            "SELECT badge_key, earned_at FROM badges WHERE user_id=? ORDER BY earned_at", (uid,)
        ).fetchall()

    if not row:
        await update.message.reply_text("Henüz streak verisi yok. Görevleri tamamlamaya başla! 💪")
        return

    cur  = row["current_streak"]
    best = row["best_streak"]
    pts  = row["total_points"] or 0

    flame     = _flame_bar(cur)
    level_name, remaining, next_thresh = get_level(pts)
    base      = next_thresh - remaining
    level_bar = progress_bar(pts - base, next_thresh - base) if next_thresh > base else progress_bar(1,1)
    calendar  = _streak_calendar(uid)

    earned_keys = {b["badge_key"] for b in badges}

    badge_lines = []
    for b in badges:
        key = b["badge_key"]
        if key in BADGE_DEFS:
            emoji, name, desc = BADGE_DEFS[key]
            badge_lines.append(f"{emoji} *{name}* — _{desc}_")
    badge_section = ("\n\n🏅 *Kazanılan Rozetler:*\n" + "\n".join(badge_lines)) if badge_lines else ""

    locked_lines = []
    for key, (emoji, name, desc) in BADGE_DEFS.items():
        if key not in earned_keys:
            locked_lines.append(f"🔒 {name} — _{desc}_")
    locked_section = ("\n\n🔒 *Kilitli Rozetler:*\n" + "\n".join(locked_lines)) if locked_lines else ""

    text = (
        f"🔥 *Streak Durumun*\n\n"
        f"{calendar}\n\n"
        f"Güncel streak: *{cur} gün*\n"
        f"{flame}\n"
        f"En iyi streak: *{best} gün* 🏆\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"⭐ *{pts} puan* · {level_name}\n"
        f"Sonraki seviyeye: *{remaining} puan*\n"
        f"{level_bar}"
        f"{badge_section}"
        f"{locked_section}"
    )

    await update.message.reply_text(text, parse_mode="Markdown")


def _flame_bar(streak: int) -> str:
    if streak == 0:
        return "💤 Henüz streak yok"
    flames = "🔥" * min(streak, 10)
    return flames + (f" ×{streak}" if streak > 10 else "")


def _streak_calendar(user_id: int) -> str:
    from datetime import date, timedelta
    today = now_tz().date()
    cells = []
    with get_conn() as con:
        for i in range(6, -1, -1):
            d   = (today - timedelta(days=i)).isoformat()
            wd  = (today - timedelta(days=i)).weekday()
            total = con.execute(
                "SELECT COUNT(*) FROM daily_logs WHERE user_id=? AND date=?", (user_id, d)
            ).fetchone()[0]
            done  = con.execute(
                "SELECT SUM(done) FROM daily_logs WHERE user_id=? AND date=?", (user_id, d)
            ).fetchone()[0] or 0
            icon = "⬜" if total == 0 else ("✅" if done == total else ("🟡" if done / total >= 0.5 else "❌"))
            cells.append(f"{day_name(wd)}\n{icon}")
    return "  ".join(cells)


# ════════════════════════════════════════════════════════════════
#  /haftalik
# ════════════════════════════════════════════════════════════════

async def cmd_weekly(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await send_weekly_report(update.message.chat_id, uid, ctx)


async def send_weekly_report(chat_id: int, user_id: int, ctx):
    with get_conn() as con:
        rows = con.execute("""
            SELECT t.title, COUNT(dl.id) AS total, SUM(dl.done) AS done
            FROM daily_logs dl JOIN tasks t ON t.id = dl.task_id
            WHERE dl.user_id=? AND dl.date >= date('now','-7 days','localtime')
            GROUP BY t.id ORDER BY done DESC
        """, (user_id,)).fetchall()

        day_rows = con.execute("""
            SELECT date, COUNT(*) AS total, SUM(done) AS done
            FROM daily_logs WHERE user_id=? AND date >= date('now','-7 days','localtime')
            GROUP BY date ORDER BY date
        """, (user_id,)).fetchall()

        cat_rows = con.execute("""
            SELECT COALESCE(c.emoji||' '||c.name, '📌 Genel') AS cat,
                   COUNT(dl.id) AS total, SUM(dl.done) AS done
            FROM daily_logs dl JOIN tasks t ON t.id = dl.task_id
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE dl.user_id=? AND dl.date >= date('now','-7 days','localtime')
            GROUP BY t.category_id ORDER BY done DESC
        """, (user_id,)).fetchall()

    if not rows:
        await ctx.bot.send_message(chat_id, "📊 Haftalık rapor için yeterli veri yok.")
        return

    total_all = sum(r["total"] for r in rows)
    done_all  = sum(r["done"]  for r in rows)
    pct_all   = round(done_all / total_all * 100) if total_all else 0

    best_day = worst_day = None
    if day_rows:
        def dpct(r): return r["done"] / r["total"] if r["total"] else 0
        best_day  = max(day_rows, key=dpct)
        worst_day = min(day_rows, key=dpct)

    chart = _daily_chart(day_rows)

    lines = [
        f"📊 *Haftalık Rapor* (Son 7 Gün)\n",
        f"Genel başarı: {progress_bar(done_all, total_all)} %{pct_all}",
        f"✅ {done_all} tamamlandı  ❌ {total_all-done_all} yapılmadı  Toplam {total_all}\n",
        chart,
    ]

    if best_day:
        bp = round(best_day["done"] / best_day["total"] * 100)
        wp = round(worst_day["done"] / worst_day["total"] * 100)
        lines += [
            f"\n🏆 En verimli: *{best_day['date']}* %{bp}",
            f"📉 En verimsiz: *{worst_day['date']}* %{wp}\n",
        ]

    if cat_rows:
        lines.append("*📂 Kategori Bazlı:*")
        for cat in cat_rows:
            p = round(cat["done"] / cat["total"] * 100) if cat["total"] else 0
            lines.append(f"{cat['cat']}: {progress_bar(cat['done'], cat['total'])} %{p}")

    lines.append("\n*📋 Görev Detayı:*")
    for r in rows:
        p = round(r["done"] / r["total"] * 100) if r["total"] else 0
        icon = "✅" if p >= 80 else ("⚠️" if p >= 40 else "❌")
        lines.append(f"{icon} {r['title']} — %{p} ({r['done']}/{r['total']})")

    await ctx.bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")


def _daily_chart(day_rows) -> str:
    if not day_rows:
        return ""
    lines = ["*📈 Günlük Grafik:*"]
    from datetime import date as dt
    for r in day_rows:
        pct    = round(r["done"] / r["total"] * 100) if r["total"] else 0
        filled = round(pct / 10)
        bar    = "█" * filled + "░" * (10 - filled)
        try:
            d     = dt.fromisoformat(r["date"])
            label = f"{day_name(d.weekday())} {r['date'][5:]}"
        except Exception:
            label = r["date"]
        lines.append(f"`{label}  {bar}  %{pct}`")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════
#  /istatistik  — sekmeli menü
# ════════════════════════════════════════════════════════════════

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await _send_stats_overview(update.message.chat_id, uid, ctx)


async def _send_stats_overview(chat_id: int, uid: int, ctx):
    with get_conn() as con:
        all_time = con.execute(
            "SELECT COUNT(*) AS total, SUM(done) AS done FROM daily_logs WHERE user_id=?", (uid,)
        ).fetchone()
        streak = con.execute("SELECT * FROM streaks WHERE user_id=?", (uid,)).fetchone()
        total_badges = con.execute("SELECT COUNT(*) FROM badges WHERE user_id=?", (uid,)).fetchone()[0]
        avg_row = con.execute("""
            SELECT AVG(day_done * 1.0 / day_total) FROM (
                SELECT SUM(done) AS day_done, COUNT(*) AS day_total
                FROM daily_logs WHERE user_id=? GROUP BY date HAVING day_total>0
            )
        """, (uid,)).fetchone()[0] or 0

    total = all_time["total"] or 0
    done  = all_time["done"]  or 0
    pct   = round(done / total * 100) if total else 0
    pts   = streak["total_points"] if streak else 0
    cur   = streak["current_streak"] if streak else 0
    level_name, remaining, _ = get_level(pts)

    text = (
        f"📈 *İstatistikler — Genel Bakış*\n\n"
        f"Toplam görev:         *{total}*\n"
        f"✅ Tamamlanan:        *{done}*\n"
        f"❌ Yapılmayan:        *{total - done}*\n"
        f"Başarı oranı:         {progress_bar(done, total)} *%{pct}*\n\n"
        f"📅 Ortalama verimlilik: *%{round(avg_row*100)}*\n"
        f"🔥 Güncel streak:      *{cur} gün*\n"
        f"⭐ Toplam puan:        *{pts}* · {level_name}\n"
        f"Sonraki seviyeye:     *{remaining} puan*\n"
        f"🏅 Rozetler:           *{total_badges}/{len(BADGE_DEFS)}*\n"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📅 Haftalık",     callback_data="stats_weekly"),
            InlineKeyboardButton("📆 Aylık",         callback_data="stats_monthly"),
        ],
        [
            InlineKeyboardButton("🏆 En İyiler",    callback_data="stats_top"),
            InlineKeyboardButton("📂 Kategori",      callback_data="stats_cat"),
        ],
        [
            InlineKeyboardButton("⏰ Saat Analizi", callback_data="stats_hour"),
        ],
    ])
    await ctx.bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=keyboard)


def _back_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Geri", callback_data="stats_back")]])


async def cb_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid  = query.from_user.id
    data = query.data

    dispatch = {
        "stats_weekly":  _stats_weekly,
        "stats_monthly": _stats_monthly,
        "stats_top":     _stats_top,
        "stats_cat":     _stats_category,
        "stats_hour":    _stats_hour,
    }

    if data in dispatch:
        await dispatch[data](query, uid, ctx)
    elif data == "stats_back":
        await query.delete_message()
        await _send_stats_overview(query.message.chat_id, uid, ctx)


async def _stats_weekly(query, uid: int, ctx):
    with get_conn() as con:
        rows = con.execute("""
            SELECT date, COUNT(*) AS total, SUM(done) AS done
            FROM daily_logs WHERE user_id=? AND date >= date('now','-7 days','localtime')
            GROUP BY date ORDER BY date
        """, (uid,)).fetchall()

    if not rows:
        await query.edit_message_text("Henüz veri yok.", reply_markup=_back_btn())
        return

    from datetime import date as dt
    lines = ["📅 *Haftalık Performans:*\n"]
    for r in rows:
        pct   = round(r["done"] / r["total"] * 100) if r["total"] else 0
        d     = dt.fromisoformat(r["date"])
        label = f"{day_name(d.weekday())} {r['date'][5:]}"
        lines.append(f"`{label}`  {progress_bar(r['done'], r['total'], 8)}  %{pct}")

    await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=_back_btn())


async def _stats_monthly(query, uid: int, ctx):
    with get_conn() as con:
        rows = con.execute("""
            SELECT strftime('%Y-%W', date) AS week, COUNT(*) AS total, SUM(done) AS done
            FROM daily_logs WHERE user_id=? AND date >= date('now','-30 days','localtime')
            GROUP BY week ORDER BY week
        """, (uid,)).fetchall()

    if not rows:
        await query.edit_message_text("Henüz veri yok.", reply_markup=_back_btn())
        return

    lines = ["📆 *Aylık Performans (Hafta Hafta):*\n"]
    for i, r in enumerate(rows, 1):
        pct = round(r["done"] / r["total"] * 100) if r["total"] else 0
        lines.append(f"Hafta {i}: {progress_bar(r['done'], r['total'], 8)} %{pct}  ({r['done']}/{r['total']})")

    total = sum(r["total"] for r in rows)
    done  = sum(r["done"]  for r in rows)
    pct   = round(done / total * 100) if total else 0
    lines.append(f"\nGenel: {progress_bar(done, total)} *%{pct}*")

    await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=_back_btn())


async def _stats_top(query, uid: int, ctx):
    with get_conn() as con:
        most_done = con.execute("""
            SELECT t.title, COUNT(*) AS cnt
            FROM daily_logs dl JOIN tasks t ON t.id=dl.task_id
            WHERE dl.user_id=? AND dl.done=1
            GROUP BY t.id ORDER BY cnt DESC LIMIT 5
        """, (uid,)).fetchall()

        most_skipped = con.execute("""
            SELECT t.title, COUNT(*) AS cnt
            FROM daily_logs dl JOIN tasks t ON t.id=dl.task_id
            WHERE dl.user_id=? AND dl.done=0
            GROUP BY t.id ORDER BY cnt DESC LIMIT 5
        """, (uid,)).fetchall()

        best_days = con.execute("""
            SELECT date, SUM(done) AS done, COUNT(*) AS total
            FROM daily_logs WHERE user_id=?
            GROUP BY date HAVING total>0
            ORDER BY (done*1.0/total) DESC, done DESC LIMIT 3
        """, (uid,)).fetchall()

    lines = ["🏆 *En İyi & En Kötü*\n"]
    if most_done:
        lines.append("*✅ En Çok Tamamlanan:*")
        for i, r in enumerate(most_done, 1):
            lines.append(f"  {i}. {r['title']} ({r['cnt']}x)")

    if most_skipped:
        lines.append("\n*❌ En Çok Atlanan:*")
        for i, r in enumerate(most_skipped, 1):
            lines.append(f"  {i}. {r['title']} ({r['cnt']}x)")

    if best_days:
        lines.append("\n*🌟 En Verimli Günler:*")
        for r in best_days:
            pct = round(r["done"] / r["total"] * 100)
            lines.append(f"  {r['date']} — %{pct} ({r['done']}/{r['total']})")

    await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=_back_btn())


async def _stats_category(query, uid: int, ctx):
    with get_conn() as con:
        rows = con.execute("""
            SELECT COALESCE(c.emoji||' '||c.name, '📌 Genel') AS cat,
                   COUNT(dl.id) AS total, SUM(dl.done) AS done
            FROM daily_logs dl JOIN tasks t ON t.id = dl.task_id
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE dl.user_id=?
            GROUP BY t.category_id ORDER BY done DESC
        """, (uid,)).fetchall()

    if not rows:
        await query.edit_message_text("Kategori verisi yok.", reply_markup=_back_btn())
        return

    lines = ["📂 *Kategori Bazlı Analiz:*\n"]
    for r in rows:
        pct = round(r["done"] / r["total"] * 100) if r["total"] else 0
        lines.append(f"*{r['cat']}*")
        lines.append(f"{progress_bar(r['done'], r['total'])} %{pct} ({r['done']}/{r['total']})\n")

    await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=_back_btn())


async def _stats_hour(query, uid: int, ctx):
    with get_conn() as con:
        rows = con.execute("""
            SELECT strftime('%H', done_at) AS hour, COUNT(*) AS cnt
            FROM daily_logs WHERE user_id=? AND done=1 AND done_at IS NOT NULL
            GROUP BY hour ORDER BY cnt DESC LIMIT 8
        """, (uid,)).fetchall()

    if not rows:
        await query.edit_message_text(
            "Henüz saat verisi yok.\nGörevleri tamamladıkça burada görünecek.",
            reply_markup=_back_btn()
        )
        return

    max_cnt     = max(r["cnt"] for r in rows)
    sorted_rows = sorted(rows, key=lambda r: r["hour"])
    lines       = ["⏰ *En Aktif Saatler:*\n"]
    for r in sorted_rows:
        bar_len = round(r["cnt"] / max_cnt * 10)
        bar     = "█" * bar_len + "░" * (10 - bar_len)
        lines.append(f"`{r['hour']}:00  {bar}  {r['cnt']}x`")

    await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=_back_btn())
