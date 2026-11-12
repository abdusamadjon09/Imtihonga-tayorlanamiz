from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def home_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 Mening fanlarim", callback_data="my_subjects"),
         InlineKeyboardButton("📖 Barcha kitoblar", callback_data="library")],
        [InlineKeyboardButton("📊 Natijalarim", callback_data="stats"),
         InlineKeyboardButton("👤 Profilim", callback_data="profile")],
        [InlineKeyboardButton("❔ Yordam", callback_data="help")]
    ])

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Kitob qo‘shish", callback_data="admin:addbook")],
        [InlineKeyboardButton("🖼 Sahifa qo‘shish", callback_data="admin:addpage")],
        [InlineKeyboardButton("📝 Sahifa testi qo‘shish", callback_data="admin:addquestion")],
        [InlineKeyboardButton("🏁 Yakuniy test savoli", callback_data="admin:addfinal")],
        [InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="admin:users")],
        [InlineKeyboardButton("📚 Kitoblar ro‘yxati", callback_data="admin:books")]
    ])

def book_keyboard(book_id, page_number):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔊 Audio tinglash", callback_data=f"audio:{book_id}:{page_number}")],
        [InlineKeyboardButton("📝 Sahifa testini boshlash", callback_data=f"quiz:page:{book_id}:{page_number}")],
        [InlineKeyboardButton("⬅️ Bosh menyu", callback_data="home")]
    ])

def answer_keyboard(session_id, question):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"A. {question['option_a']}", callback_data=f"ans:{session_id}:A")],
        [InlineKeyboardButton(f"B. {question['option_b']}", callback_data=f"ans:{session_id}:B")],
        [InlineKeyboardButton(f"C. {question['option_c']}", callback_data=f"ans:{session_id}:C")],
        [InlineKeyboardButton(f"D. {question['option_d']}", callback_data=f"ans:{session_id}:D")]
    ])
