import os
from zoneinfo import ZoneInfo

TOKEN    = os.environ.get("TELEGRAM_TOKEN", "YOUR_TOKEN_HERE")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))   # sadece bu user_id kullanabilir (0 = herkese açık)
TZ_STR   = os.environ.get("TZ", "Europe/Istanbul")
TZ       = ZoneInfo(TZ_STR)

# Sabah planı saati
MORNING_HOUR   = int(os.environ.get("MORNING_HOUR", "8"))
MORNING_MINUTE = int(os.environ.get("MORNING_MINUTE", "0"))

# Gün sonu raporu
EVENING_HOUR   = int(os.environ.get("EVENING_HOUR", "21"))
EVENING_MINUTE = int(os.environ.get("EVENING_MINUTE", "0"))

# Haftalık rapor (Pazar)
WEEKLY_HOUR   = int(os.environ.get("WEEKLY_HOUR", "20"))
WEEKLY_MINUTE = int(os.environ.get("WEEKLY_MINUTE", "0"))

# Gün içi rastgele soru — kaç saatte bir (0 = kapalı)
RANDOM_CHECK_HOURS = int(os.environ.get("RANDOM_CHECK_HOURS", "3"))

PRIORITY_EMOJI = {"yüksek": "🔴", "orta": "🟡", "düşük": "🟢"}
TYPE_LABEL     = {"daily": "Günlük", "weekly": "Haftalık", "once": "Tek seferlik", "recurring": "Tekrarlayan"}

ACTIVITY_OPTIONS = [
    ("💼 Çalışıyorum",   "work"),
    ("📚 Ders/Okuma",    "study"),
    ("📱 Sosyal medya",  "social"),
    ("😴 Dinleniyorum",  "rest"),
    ("🏃 Spor",          "sport"),
    ("🍽 Yemek",          "food"),
    ("🎮 Eğlence",       "entertainment"),
    ("🕌 İbadet",        "prayer"),
]

BADGE_DEFS = {
    "first_task":    ("🌱", "İlk Adım",      "İlk görevini tamamladın!"),
    "streak_3":      ("🔥", "Alev Al",        "3 gün üst üste!"),
    "streak_7":      ("⚡", "Odak Ustası",    "7 günlük streak!"),
    "streak_30":     ("👑", "Disiplin Ustası","30 günlük streak!"),
    "perfect_day":   ("⭐", "Mükemmel Gün",   "Bugün tüm görevleri tamamladın!"),
    "early_bird":    ("🌅", "Erken Kuş",      "Sabah 7'den önce görev tamamladın!"),
    "century":       ("💯", "Yüzlük",         "100 görev tamamladın!"),
    "productive":    ("🚀", "Üretken",        "Bir haftada 50+ görev!"),
}
