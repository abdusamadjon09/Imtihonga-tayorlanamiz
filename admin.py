from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_ID
from database.db import get_connection
from bot.keyboards import admin_keyboard

def is_admin(uid):
    return ADMIN_ID != 0 and uid == ADMIN_ID

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Bu panel faqat bosh administrator uchun.")
        return
    await update.message.reply_text("🛠 IMTIHON USTOZ — ADMIN PANEL", reply_markup=admin_keyboard())

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    if not is_admin(uid):
        await q.message.reply_text("Ruxsat yo‘q.")
        return
    action = q.data.split(":")[1]
    prompts = {
        "addbook": "Kitob yuboring: SINF|FAN|KITOB NOMI|IZOH",
        "addpage": "Sahifa yuboring: KITOB_ID|SAHIFA_RAQAMI|SAHIFA NOMI|MATN. "
                   "Keyin shu sahifa uchun rasm yuboring yoki /skipphoto yozing. "
                   "So‘ng audio yuboring yoki /skipaudio yozing.",
        "addquestion": "Test yuboring: SAHIFA_ID|SAVOL|A|B|C|D|TO‘G‘RI_JAVOB",
        "addfinal": "Yakuniy test savoli: KITOB_ID|SAVOL|A|B|C|D|TO‘G‘RI_JAVOB"
    }
    if action in prompts:
        context.user_data["admin_action"] = action
        await q.message.reply_text(prompts[action])
    elif action == "users":
        with get_connection() as con:
            count = con.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
            rows = con.execute(
                "SELECT telegram_id,username,full_name,grade,subjects FROM users ORDER BY created_at DESC LIMIT 30"
            ).fetchall()
        text = f"👥 Jami: {count}\n\n"
        for r in rows:
            text += (
                f"{r['full_name']} | {r['grade']}-sinf | {r['subjects']}\n"
                f"Telegram ID: {r['telegram_id']} | @{r['username'] or 'username yo‘q'}\n\n"
            )
        await q.message.reply_text(text[:4000])
    elif action == "books":
        with get_connection() as con:
            rows = con.execute("SELECT id,grade,subject,title FROM books ORDER BY id DESC LIMIT 50").fetchall()
        text = "📚 Kitoblar:\n" + "\n".join(
            f"ID {r['id']} | {r['grade']}-sinf | {r['subject']} | {r['title']}" for r in rows
        )
        await q.message.reply_text(text[:4000] or "Kitoblar yo‘q.")

async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get("admin_action")
    if not action:
        return
    if not is_admin(update.effective_user.id):
        return
    text = update.message.text.strip()
    parts = text.split("|")
    try:
        with get_connection() as con:
            if action == "addbook":
                if len(parts) < 3:
                    raise ValueError("Format: SINF|FAN|KITOB NOMI|IZOH")
                grade = int(parts[0])
                if not 1 <= grade <= 11:
                    raise ValueError("Sinf 1–11 oralig‘ida bo‘lsin.")
                con.execute(
                    "INSERT INTO books(grade,subject,title,description) VALUES(?,?,?,?)",
                    (grade, parts[1].strip(), parts[2].strip(), parts[3].strip() if len(parts)>3 else "")
                )
                context.user_data.pop("admin_action", None)
                await update.message.reply_text("✅ Kitob qo‘shildi. /admin → Kitoblar ro‘yxati orqali ID ni ko‘ring.")
            elif action == "addpage":
                if len(parts) < 4:
                    raise ValueError("Format: KITOB_ID|SAHIFA_RAQAMI|SAHIFA NOMI|MATN")
                book_id, page_no = int(parts[0]), int(parts[1])
                title, body = parts[2].strip(), "|".join(parts[3:]).strip()
                cur = con.execute(
                    """INSERT INTO pages(book_id,page_number,title,body)
                    VALUES(?,?,?,?) ON CONFLICT(book_id,page_number) DO UPDATE SET
                    title=excluded.title,body=excluded.body""",
                    (book_id, page_no, title, body)
                )
                row = con.execute(
                    "SELECT id FROM pages WHERE book_id=? AND page_number=?", (book_id,page_no)
                ).fetchone()
                context.user_data["pending_page_id"] = row["id"]
                context.user_data["admin_action"] = "page_photo"
                await update.message.reply_text(
                    f"✅ Sahifa matni saqlandi. Sahifa ID: {row['id']}\n"
                    "Endi shu sahifa uchun rasm yuboring yoki /skipphoto yozing."
                )
            elif action == "addquestion":
                if len(parts) != 7:
                    raise ValueError("7 ta maydon bo‘lishi kerak.")
                page_id = int(parts[0]); correct = parts[6].upper()
                if correct not in "ABCD" or len(correct) != 1:
                    raise ValueError("To‘g‘ri javob A/B/C/D bo‘lsin.")
                con.execute(
                    """INSERT INTO page_questions
                    (page_id,question,option_a,option_b,option_c,option_d,correct_answer)
                    VALUES(?,?,?,?,?,?,?)""",
                    (page_id, *[x.strip() for x in parts[1:6]], correct)
                )
                context.user_data.pop("admin_action", None)
                await update.message.reply_text("✅ Sahifa testi savoli qo‘shildi.")
            elif action == "addfinal":
                if len(parts) != 7:
                    raise ValueError("7 ta maydon bo‘lishi kerak.")
                book_id = int(parts[0]); correct = parts[6].upper()
                if correct not in "ABCD" or len(correct) != 1:
                    raise ValueError("To‘g‘ri javob A/B/C/D bo‘lsin.")
                con.execute(
                    """INSERT INTO final_questions
                    (book_id,question,option_a,option_b,option_c,option_d,correct_answer)
                    VALUES(?,?,?,?,?,?,?)""",
                    (book_id, *[x.strip() for x in parts[1:6]], correct)
                )
                context.user_data.pop("admin_action", None)
                await update.message.reply_text("✅ Yakuniy imtihon savoli qo‘shildi.")
    except Exception as exc:
        await update.message.reply_text(f"Xatolik: {exc}\nFormatni tekshirib qayta yuboring.")

async def admin_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    action = context.user_data.get("admin_action")
    if action == "page_photo":
        page_id = context.user_data.get("pending_page_id")
        if not page_id:
            return
        file_id = update.message.photo[-1].file_id
        with get_connection() as con:
            con.execute("UPDATE pages SET image_file_id=? WHERE id=?", (file_id,page_id))
        context.user_data["admin_action"] = "page_audio"
        await update.message.reply_text("🖼 Rasm saqlandi. Endi audio yuboring yoki /skipaudio yozing.")

async def admin_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if context.user_data.get("admin_action") != "page_audio":
        return
    page_id = context.user_data.get("pending_page_id")
    if not page_id or not update.message.audio:
        return
    with get_connection() as con:
        con.execute("UPDATE pages SET audio_file_id=? WHERE id=?", (update.message.audio.file_id,page_id))
    context.user_data.pop("admin_action", None)
    context.user_data.pop("pending_page_id", None)
    await update.message.reply_text("🎧 Audio saqlandi. Sahifa to‘liq qo‘shildi.")

async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("admin_action") != "page_photo":
        await update.message.reply_text("Hozir rasm bosqichi emas.")
        return
    context.user_data["admin_action"] = "page_audio"
    await update.message.reply_text("Rasmsiz davom etamiz. Audio yuboring yoki /skipaudio yozing.")

async def skip_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("admin_action") != "page_audio":
        await update.message.reply_text("Hozir audio bosqichi emas.")
        return
    context.user_data.pop("admin_action", None)
    context.user_data.pop("pending_page_id", None)
    await update.message.reply_text("✅ Sahifa saqlandi (audiosiz).")
