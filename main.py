#!/usr/bin/env python3
"""
Günlük Görev Takip Botu — Ana Giriş Noktası
"""
import logging
from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

from config import TOKEN, OWNER_ID
from database import init_db, get_conn
from handlers.tasks import (
    build_add_task_conv, cmd_delete_task, cmd_list_tasks,
    cmd_add_category, cb_delete_task
)
from handlers.daily import (
    cmd_today, cb_check, cb_snooze, cb_snooze_set,
    cmd_ne_yapiyorsun, cb_activity
)
from handlers.stats import cmd_streak, cmd_weekly, cmd_stats, cb_stats
from jobs.scheduler import register_jobs

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.first_name or "Kullanıcı"

    with get_conn() as con:
        con.execute(
            "INSERT OR IGNORE INTO users(user_id, username) VALUES(?,?)",
            (uid, update.effective_user.username)
        )
        con.commit()

    await update.message.reply_text(
        f"👋 Merhaba *{name}!*\n\n"
        "📋 *Günlük Görev Takip Botuna Hoş Geldin!*\n\n"
        "━━━━━━━━━━━━━━━\n"
        "📌 *Görev Yönetimi*\n"
        "/gorev\\_ekle — Yeni görev ekle\n"
        "/gorevler — Tüm görevleri listele\n"
        "/gorev\\_sil — Görev sil\n"
        "/kategori\\_ekle 🏃 Spor — Kategori ekle\n\n"
        "📅 *Günlük Takip*\n"
        "/bugun — Bugünkü planı gör & işaretle\n"
        "/ne\\_yapiyorsun — Anlık aktivite kaydet\n\n"
        "📊 *Raporlar*\n"
        "/haftalik — Haftalık analiz\n"
        "/istatistik — Tüm zamanların istatistiği\n"
        "/streak — Streak & rozetler\n\n"
        "━━━━━━━━━━━━━━━\n"
        "⏰ *Otomatik bildirimler:*\n"
        "🌅 08:00 — Sabah planı\n"
        "🌙 21:00 — Gün sonu özeti\n"
        "📊 Pazar 20:00 — Haftalık rapor",
        parse_mode="Markdown"
    )


# ── /plan ─────────────────────────────────────────────────────────────────────

async def cmd_plan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Bugünkü planı göster (alias for /bugun)"""
    await cmd_today(update, ctx)


# ── /yardim ───────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, ctx)


# ── Middleware: sadece owner ───────────────────────────────────────────────────

async def owner_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if OWNER_ID and update.effective_user and update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Bu bot sadece özel kullanım için.")
        return


# ── Ana fonksiyon ─────────────────────────────────────────────────────────────

async def post_init(app: Application):
    """Bot başladığında komut menüsünü kaydet."""
    commands = [
        BotCommand("start",           "Botu başlat"),
        BotCommand("bugun",           "Bugünkü planı gör"),
        BotCommand("plan",            "Bugünkü planı gör"),
        BotCommand("gorev_ekle",      "Yeni görev ekle"),
        BotCommand("gorevler",        "Görevleri listele"),
        BotCommand("gorev_sil",       "Görev sil"),
        BotCommand("kategori_ekle",   "Kategori ekle"),
        BotCommand("ne_yapiyorsun",   "Anlık aktivite kaydet"),
        BotCommand("haftalik",        "Haftalık rapor"),
        BotCommand("istatistik",      "İstatistikler"),
        BotCommand("streak",          "Streak & rozetler"),
        BotCommand("yardim",          "Yardım"),
    ]
    await app.bot.set_my_commands(commands)
    logger.info("✅ Bot başlatıldı!")


def main():
    init_db()

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    # Görev ekleme (ConversationHandler — önce kayıt edilmeli)
    app.add_handler(build_add_task_conv())

    # Komutlar
    app.add_handler(CommandHandler("start",          cmd_start))
    app.add_handler(CommandHandler("yardim",         cmd_help))
    app.add_handler(CommandHandler("plan",           cmd_plan))
    app.add_handler(CommandHandler("bugun",          cmd_today))
    app.add_handler(CommandHandler("gorevler",       cmd_list_tasks))
    app.add_handler(CommandHandler("gorev_sil",      cmd_delete_task))
    app.add_handler(CommandHandler("kategori_ekle",  cmd_add_category))
    app.add_handler(CommandHandler("ne_yapiyorsun",  cmd_ne_yapiyorsun))
    app.add_handler(CommandHandler("haftalik",       cmd_weekly))
    app.add_handler(CommandHandler("istatistik",     cmd_stats))
    app.add_handler(CommandHandler("streak",         cmd_streak))

    # Callback butonlar
    app.add_handler(CallbackQueryHandler(cb_check,      pattern=r"^chk_"))
    app.add_handler(CallbackQueryHandler(cb_snooze_set, pattern=r"^snz_"))
    app.add_handler(CallbackQueryHandler(cb_snooze,     pattern=r"^snooze_\d+"))
    app.add_handler(CallbackQueryHandler(cb_delete_task,pattern=r"^deltask_"))
    app.add_handler(CallbackQueryHandler(cb_activity,   pattern=r"^act_"))
    app.add_handler(CallbackQueryHandler(cb_stats,      pattern=r"^stats_"))

    # Zamanlayıcılar
    register_jobs(app)

    logger.info("🚀 Polling başlatılıyor...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
