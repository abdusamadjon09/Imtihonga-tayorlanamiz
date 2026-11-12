from telegram import Update
from telegram.ext import ContextTypes
from database_db import get_connection
from keyboards import answer_keyboard
from content import get_page, get_page_questions, get_final_questions, get_book, next_page_number
from services_quizzes import create_quiz, get_session, get_question, answer_question
from library import send_page

async def start_quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    quiz_type, book_id, page_number = parts[1], int(parts[2]), int(parts[3])
    book = get_book(book_id)
    if quiz_type == "page":
        page = get_page(book_id, page_number)
        questions = get_page_questions(page["id"]) if page else []
        if not questions:
            await q.message.reply_text("Bu sahifa uchun test savollari hali kiritilmagan.")
            return
    else:
        questions = get_final_questions(book_id)
        if not questions:
            await q.message.reply_text("Kitob yakuniy testi hali kiritilmagan. Admin test qo‘shishi kerak.")
            return
    session_id = create_quiz(q.from_user.id, book_id, page_number, quiz_type, questions)
    ids = __import__("json").loads(
        get_session(session_id, q.from_user.id)["question_ids"]
    )
    first = get_question(ids[0])
    await q.message.reply_text(
        f"📝 {'Sahifa testi' if quiz_type == 'page' else 'Kitob yakuniy imtihoni'}\n"
        f"1/{len(ids)}. {first['question']}",
        reply_markup=answer_keyboard(session_id, first)
    )

async def answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, session_id, answer = q.data.split(":")
    session_id = int(session_id)
    result = answer_question(session_id, q.from_user.id, answer)
    if result is None:
        await q.message.reply_text("Test sessiyasi topilmadi yoki muddati tugagan. Testni qayta boshlang.")
        return
    if not result["finished"]:
        if not result["correct"]:
            await q.message.reply_text("❌ Bu javob noto‘g‘ri.")
        else:
            await q.message.reply_text("✅ To‘g‘ri!")
        # Current question index has advanced; get next ID from session.
        import json
        session = get_session(session_id, q.from_user.id)
        ids = json.loads(session["question_ids"])
        next_id = ids[session["current_index"]]
        next_q = get_question(next_id)
        await q.message.reply_text(
            f"{result['number']}/{result['total']}. {next_q['question']}",
            reply_markup=answer_keyboard(session_id, next_q)
        )
        return

    percent = result["percent"]
    if result["quiz_type"] == "page":
        if result["passed"]:
            next_number = next_page_number(result["book_id"], result["page_number"])
            if next_number is not None:
                with get_connection() as con:
                    con.execute(
                        """INSERT INTO progress(telegram_id,book_id,unlocked_page,finished)
                        VALUES(?,?,?,0)
                        ON CONFLICT(telegram_id,book_id) DO UPDATE SET
                        unlocked_page=MAX(unlocked_page,excluded.unlocked_page)""",
                        (q.from_user.id, result["book_id"], next_number)
                    )
                await q.message.reply_text(
                    f"🎉 {percent}% — 70% dan yuqori! Keyingi sahifa ochildi.",
                    reply_markup=None
                )
                book = get_book(result["book_id"])
                page = get_page(result["book_id"], next_number)
                await send_page(q.message, book, page)
            else:
                await q.message.reply_text(
                    f"🏁 Oxirgi sahifa testi tugadi: {percent}%.\n"
                    "Endi kitobning yakuniy imtihonini topshiring.",
                    reply_markup=None
                )
                await q.message.reply_text(
                    "Yakuniy imtihonni boshlash:",
                    reply_markup=__import__("telegram").InlineKeyboardMarkup([[
                        __import__("telegram").InlineKeyboardButton(
                            "🏁 Yakuniy imtihon",
                            callback_data=f"quiz:final:{result['book_id']}:0"
                        )
                    ]])
                )
        else:
            await q.message.reply_text(
                f"Natija: {percent}%. O‘tish uchun kamida 70% kerak. "
                "Sahifani qayta o‘qib, testni qayta ishlang."
            )
    else:
        if result["passed"]:
            with get_connection() as con:
                con.execute(
                    """INSERT INTO progress(telegram_id,book_id,unlocked_page,finished)
                    VALUES(?,?,1,1)
                    ON CONFLICT(telegram_id,book_id) DO UPDATE SET finished=1""",
                    (q.from_user.id, result["book_id"])
                )
            await q.message.reply_text(
                f"🏆 Tabriklaymiz! Yakuniy imtihondan {percent}% bilan o‘tdingiz. "
                "Kitob tugallandi!"
            )
        else:
            await q.message.reply_text(
                f"Yakuniy natija: {percent}%. O‘tish uchun kamida 70% kerak. "
                "Mavzularni takrorlab, qayta urinib ko‘ring."
            )
