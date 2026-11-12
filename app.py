import asyncio
import logging
import threading
from flask import Flask, jsonify
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
from config import BOT_TOKEN, PORT
from database_db import init_db
from bot.handlers.registration import (
    start, cancel, name_step, grade_step, university_step, direction_step,
    subjects_step, NAME, GRADE, UNIVERSITY, DIRECTION, SUBJECTS
)
from bot.handlers.library import show_home_callback
from bot.handlers.quizzes import start_quiz_callback, answer_callback
from bot.handlers.admin import (
    admin_command, admin_callback, admin_text, admin_photo, admin_audio,
    skip_photo, skip_audio
)
from bot.handlers.profile import profile_callback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("imtihon-ustoz")
web = Flask(__name__)

@web.get("/")
def index():
    return jsonify({"service": "IMTIHON USTOZ", "status": "running"})

@web.get("/health")
def health():
    return jsonify({"ok": True})

def start_telegram_bot():
    if not BOT_TOKEN:
        log.error("BOT_TOKEN sozlanmagan. Render Environment Variables ni tekshiring.")
        return

    # Python 3.14 da yangi thread ichida event loop avtomatik yaratilmaydi.
    # python-telegram-bot run_polling() shu loopdan foydalanadi.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    application = Application.builder().token(BOT_TOKEN).build()

    registration = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_step)],
            GRADE: [MessageHandler(filters.TEXT & ~filters.COMMAND, grade_step)],
            UNIVERSITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, university_step)],
            DIRECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, direction_step)],
            SUBJECTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, subjects_step)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    application.add_handler(registration)
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("skipphoto", skip_photo))
    application.add_handler(CommandHandler("skipaudio", skip_audio))

    application.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin:"))
    application.add_handler(CallbackQueryHandler(start_quiz_callback, pattern=r"^quiz:"))
    application.add_handler(CallbackQueryHandler(answer_callback, pattern=r"^ans:"))
    application.add_handler(CallbackQueryHandler(show_home_callback, pattern=r"^(home|library|my_subjects|book:|audio:)"))
    application.add_handler(CallbackQueryHandler(profile_callback, pattern=r"^(profile|stats|help)$"))

    application.add_handler(MessageHandler(filters.PHOTO, admin_photo))
    application.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, admin_audio))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text))

    log.info("Telegram bot polling boshlandi")
    try:
        application.run_polling(drop_pending_updates=True)
    except Exception:
        log.exception("Telegram bot ishga tushishida xatolik yuz berdi")
    finally:
        if not loop.is_closed():
            loop.close()
        asyncio.set_event_loop(None)

init_db()
# Single Gunicorn worker is required for the in-process polling thread.
if not globals().get("_BOT_THREAD_STARTED", False):
    _BOT_THREAD_STARTED = True
    threading.Thread(target=start_telegram_bot, daemon=True, name="telegram-polling").start()

if __name__ == "__main__":
    web.run(host="0.0.0.0", port=PORT)
