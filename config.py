import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/imtihon_ustoz.db")
PORT = int(os.getenv("PORT", "10000"))
PASS_PERCENT = 70
PAGE_QUESTIONS_DEFAULT = 5
FINAL_QUESTIONS_DEFAULT = 20
