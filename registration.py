from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database_db import get_connection
from keyboards import home_keyboard

NAME, GRADE, UNIVERSITY, DIRECTION, SUBJECTS = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    with get_connection() as con:
        user = con.execute("SELECT telegram_id FROM users WHERE telegram_id=?", (uid,)).fetchone()
    if user:
        await update.message.reply_text(
            "Assalomu alaykum! IMTIHON USTOZ botiga xush kelibsiz.",
            reply_markup=home_keyboard()
        )
        return ConversationHandler.END
    await update.message.reply_text(
        "Assalomu alaykum! Ro‘yxatdan o‘tamiz.\nIsm va familiyangizni yozing:"
    )
    return NAME

async def name_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2 or len(name) > 100:
        await update.message.reply_text("Ism-familiyani 2–100 belgi oralig‘ida kiriting.")
        return NAME
    context.user_data["full_name"] = name
    await update.message.reply_text("Nechanchi sinfda o‘qiysiz? 1 dan 11 gacha kiriting.")
    return GRADE

async def grade_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    if not value.isdigit() or not 1 <= int(value) <= 11:
        await update.message.reply_text("Sinf 1–11 oralig‘ida bo‘lishi kerak.")
        return GRADE
    context.user_data["grade"] = int(value)
    await update.message.reply_text("Qaysi oliygohga yoki ta’lim muassasasiga kirmoqchisiz?")
    return UNIVERSITY

async def university_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["university"] = update.message.text.strip()[:160]
    await update.message.reply_text("Qaysi yo‘nalishga topshirmoqchisiz?")
    return DIRECTION

async def direction_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["direction"] = update.message.text.strip()[:160]
    await update.message.reply_text(
        "Qaysi fanlar blokini tanlagansiz? Fanlarni vergul bilan yozing.\n"
        "Masalan: Matematika, Fizika"
    )
    return SUBJECTS

async def subjects_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    subjects = update.message.text.strip()[:300]
    with get_connection() as con:
        con.execute(
            """INSERT OR REPLACE INTO users
            (telegram_id,username,full_name,grade,university,direction,subjects)
            VALUES(?,?,?,?,?,?,?)""",
            (user.id, user.username or "", context.user_data["full_name"],
             context.user_data["grade"], context.user_data["university"],
             context.user_data["direction"], subjects)
        )
    context.user_data.clear()
    await update.message.reply_text(
        "✅ Ro‘yxatdan o‘tish tugadi! Sizga mos kitoblar “Mening fanlarim” bo‘limida.",
        reply_markup=home_keyboard()
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Bekor qilindi. Qayta boshlash uchun /start bosing.")
    return ConversationHandler.END
