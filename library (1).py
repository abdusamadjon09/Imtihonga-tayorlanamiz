from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database_db import get_connection
from keyboards import home_keyboard, book_keyboard
from content import list_books, get_book, get_page, user_progress

async def show_home_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid, data = q.from_user.id, q.data

    if data == "home":
        await q.message.reply_text("🏠 Bosh menyu", reply_markup=home_keyboard())
        return

    if data in ("library", "my_subjects"):
        books = list_books()
        if data == "my_subjects":
            with get_connection() as con:
                user = con.execute("SELECT subjects FROM users WHERE telegram_id=?", (uid,)).fetchone()
            if not user:
                await q.message.reply_text("Avval /start orqali ro‘yxatdan o‘ting.")
                return
            wanted = [s.strip().casefold() for s in user["subjects"].split(",") if s.strip()]
            books = [b for b in books if any(w in b["subject"].casefold() for w in wanted)]
        if not books:
            await q.message.reply_text("Hozircha mos kitob topilmadi. Admin kitoblarni joylashi kerak.")
            return
        buttons = [
            [InlineKeyboardButton(
                f"{b['grade']}-sinf • {b['subject']} • {b['title'][:25]}",
                callback_data=f"book:{b['id']}"
            )] for b in books
        ]
        await q.message.reply_text("📚 Kitoblar:", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data.startswith("book:"):
        book_id = int(data.split(":")[1])
        book = get_book(book_id)
        if not book:
            await q.message.reply_text("Kitob topilmadi.")
            return
        progress = user_progress(uid, book_id)
        page_number = progress["unlocked_page"] if progress else 1
        page = get_page(book_id, page_number)
        if not page:
            with get_connection() as con:
                first = con.execute(
                    "SELECT MIN(page_number) n FROM pages WHERE book_id=?", (book_id,)
                ).fetchone()["n"]
            if first is None:
                await q.message.reply_text("Bu kitobga sahifalar hali kiritilmagan.")
                return
            page_number = first
            page = get_page(book_id, page_number)
        await send_page(q.message, book, page)
        return

    if data.startswith("audio:"):
        _, book_id, page_number = data.split(":")
        page = get_page(int(book_id), int(page_number))
        if page and page["audio_file_id"]:
            await q.message.reply_audio(page["audio_file_id"], caption="🔊 Audio dars")
        else:
            await q.message.reply_text("Bu sahifa uchun audio hali yuklanmagan.")
        return

async def send_page(message, book, page):
    title = page["title"] or f"{page['page_number']}-sahifa"
    caption = (
        f"📖 {book['title']}\n{title}\n\n{page['body']}\n\n"
        "Sahifani o‘qib bo‘lgach, testni boshlang. Kamida 70% kerak."
    )
    keyboard = book_keyboard(book["id"], page["page_number"])
    if page["image_file_id"]:
        await message.reply_photo(page["image_file_id"], caption=caption[:1024], reply_markup=keyboard)
        if len(caption) > 1024:
            await message.reply_text(caption[1024:])
    else:
        await message.reply_text(caption, reply_markup=keyboard)
