from database_db import get_connection

def list_books():
    with get_connection() as con:
        return con.execute(
            "SELECT * FROM books WHERE active=1 ORDER BY grade, subject, title"
        ).fetchall()

def get_book(book_id):
    with get_connection() as con:
        return con.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()

def get_page(book_id, page_number):
    with get_connection() as con:
        return con.execute(
            "SELECT * FROM pages WHERE book_id=? AND page_number=?",
            (book_id, page_number)
        ).fetchone()

def get_page_questions(page_id):
    with get_connection() as con:
        return con.execute(
            "SELECT * FROM page_questions WHERE page_id=? ORDER BY id", (page_id,)
        ).fetchall()

def get_final_questions(book_id):
    with get_connection() as con:
        return con.execute(
            "SELECT * FROM final_questions WHERE book_id=? ORDER BY id", (book_id,)
        ).fetchall()

def user_progress(user_id, book_id):
    with get_connection() as con:
        return con.execute(
            "SELECT * FROM progress WHERE telegram_id=? AND book_id=?",
            (user_id, book_id)
        ).fetchone()

def next_page_number(book_id, current):
    with get_connection() as con:
        row = con.execute(
            "SELECT MIN(page_number) n FROM pages WHERE book_id=? AND page_number>?",
            (book_id, current)
        ).fetchone()
        return row["n"] if row and row["n"] is not None else None
