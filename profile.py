from telegram import Update
from telegram.ext import ContextTypes
from database.db import get_connection

async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid, data = q.from_user.id, q.data
    if data == "profile":
        with get_connection() as con:
            u = con.execute("SELECT * FROM users WHERE telegram_id=?", (uid,)).fetchone()
        if not u:
            await q.message.reply_text("Profil topilmadi. /start bosing.")
            return
        await q.message.reply_text(
            f"👤 {u['full_name']}\nSinf: {u['grade']}\n"
            f"Oliygoh: {u['university']}\nYo‘nalish: {u['direction']}\n"
            f"Fanlar: {u['subjects']}\nTelegram ID: {u['telegram_id']}"
        )
    elif data == "stats":
        with get_connection() as con:
            row = con.execute(
                "SELECT COUNT(*) n, AVG(percent) avg FROM attempts WHERE telegram_id=?", (uid,)
            ).fetchone()
            finished = con.execute(
                "SELECT COUNT(*) n FROM progress WHERE telegram_id=? AND finished=1", (uid,)
            ).fetchone()["n"]
        await q.message.reply_text(
            f"📊 Natijalar\nUrinishlar: {row['n']}\n"
            f"O‘rtacha ball: {round(row['avg'] or 0,1)}%\n"
            f"Tugatilgan kitoblar: {finished}"
        )
    elif data == "help":
        await q.message.reply_text(
            "📌 Kitob tanlang → sahifani o‘qing → sahifa testini ishlang. "
            "70% yoki undan yuqori natija keyingi sahifani ochadi. "
            "Oxirgi sahifadan keyin yakuniy imtihon topshirasiz."
        )
