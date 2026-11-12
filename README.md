# Imtihon Ustoz — Telegram bot

Kitoblarni varaq-varaq o'qish, har varaqdan test (70% o'tish), audio, yakuniy test, admin panel.

## Ishga tushirish
1. `BOT_TOKEN` va `ADMIN_IDS` (Telegram ID) o'zgaruvchilarini qo'ying (`.env.example` ga qarang)
2. `pip install -r requirements.txt`
3. `python bot.py`

## Kitob qo'shish
Botda `/admin` → «Kitob qo'shish (PDF)» → `5|Matematika|Algebra` → PDF yuboring.
Katta fayllar: `books_inbox/` ga `5-sinf__Matematika__Algebra.pdf` nomi bilan qo'ying → «Papkadan import».
