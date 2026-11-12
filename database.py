import os
import sqlite3
from config import DATABASE_PATH

def get_connection():
    folder = os.path.dirname(DATABASE_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    con = sqlite3.connect(DATABASE_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    return con

def init_db():
    with get_connection() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            full_name TEXT NOT NULL,
            grade INTEGER NOT NULL,
            university TEXT NOT NULL,
            direction TEXT NOT NULL,
            subjects TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grade INTEGER NOT NULL,
            subject TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            page_number INTEGER NOT NULL,
            title TEXT DEFAULT '',
            body TEXT NOT NULL,
            image_file_id TEXT DEFAULT '',
            audio_file_id TEXT DEFAULT '',
            UNIQUE(book_id, page_number)
        );

        CREATE TABLE IF NOT EXISTS page_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
            question TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_answer TEXT NOT NULL CHECK(correct_answer IN ('A','B','C','D'))
        );

        CREATE TABLE IF NOT EXISTS final_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            question TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_answer TEXT NOT NULL CHECK(correct_answer IN ('A','B','C','D'))
        );

        CREATE TABLE IF NOT EXISTS progress (
            telegram_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
            book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            unlocked_page INTEGER NOT NULL DEFAULT 1,
            finished INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(telegram_id, book_id)
        );

        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            page_number INTEGER NOT NULL,
            exam_type TEXT NOT NULL,
            percent REAL NOT NULL,
            correct_count INTEGER NOT NULL,
            total_count INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS quiz_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            page_number INTEGER NOT NULL,
            quiz_type TEXT NOT NULL,
            question_ids TEXT NOT NULL,
            current_index INTEGER NOT NULL DEFAULT 0,
            correct_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_books_grade_subject ON books(grade, subject);
        CREATE INDEX IF NOT EXISTS idx_pages_book_number ON pages(book_id, page_number);
        CREATE INDEX IF NOT EXISTS idx_attempts_user ON attempts(telegram_id);
        """)
