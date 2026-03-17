# 📋 Sebat — Günlük Görev Takip Botu

Sebat, Telegram üzerinden çalışan kişisel bir görev takip botudur. Sabah planını gönderir, akşam muhasebesini yapar, streak ve rozet sistemiyle motivasyonunu canlı tutar.

## ✨ Özellikler

- 📌 Günlük, haftalık, tekrarlayan ve tek seferlik görevler
- 🗂 Kategori ve öncelik sistemi
- ⏰ Görev saati bildirimi ve erteleme (10dk / 30dk / 1 saat)
- ☀️ Sabah 08:00 — günlük plan
- 🌙 Gece 21:00 — gün sonu özeti
- 📊 Pazar 20:00 — haftalık analiz raporu
- 🔥 Streak sistemi
- 🏅 Rozet sistemi
- ⭐ Puan ve seviye sistemi
- 📈 Haftalık, aylık istatistikler

## 💬 Komutlar

| Komut | Açıklama |
|---|---|
| `/start` | Botu başlat |
| `/gorev_ekle` | Yeni görev ekle |
| `/gorevler` | Görevleri listele |
| `/gorev_sil` | Görev sil |
| `/bugun` | Bugünkü planı gör |
| `/haftalik` | Haftalık rapor |
| `/istatistik` | İstatistikler |
| `/streak` | Streak & rozetler |

## 🛠 Kurulum
```bash
pip install -r requirements.txt
export TELEGRAM_TOKEN="token"
export OWNER_ID="telegram_id"
python main.py
```

## 🗄 Veritabanı

SQLite ile çalışır, tüm veriler yerel olarak saklanır.
