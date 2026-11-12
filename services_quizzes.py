import json
import random
from database_db import get_connection
from config import PASS_PERCENT

def create_quiz(user_id, book_id, page_number, quiz_type, questions):
    ids = [q["id"] for q in questions]
    random.shuffle(ids)
    with get_connection() as con:
        cur = con.execute(
            """INSERT INTO quiz_sessions
            (telegram_id,book_id,page_number,quiz_type,question_ids)
            VALUES(?,?,?,?,?)""",
            (user_id, book_id, page_number, quiz_type, json.dumps(ids))
        )
        return cur.lastrowid

def get_session(session_id, user_id):
    with get_connection() as con:
        return con.execute(
            "SELECT * FROM quiz_sessions WHERE id=? AND telegram_id=?",
            (session_id, user_id)
        ).fetchone()

def get_question(question_id):
    with get_connection() as con:
        return con.execute(
            """SELECT id,question,option_a,option_b,option_c,option_d,correct_answer
            FROM page_questions WHERE id=?
            UNION ALL
            SELECT id,question,option_a,option_b,option_c,option_d,correct_answer
            FROM final_questions WHERE id=? LIMIT 1""",
            (question_id, question_id)
        ).fetchone()

def answer_question(session_id, user_id, answer):
    with get_connection() as con:
        session = con.execute(
            "SELECT * FROM quiz_sessions WHERE id=? AND telegram_id=?",
            (session_id, user_id)
        ).fetchone()
        if not session:
            return None
        ids = json.loads(session["question_ids"])
        index = session["current_index"]
        if index >= len(ids):
            return {"finished": True}
        qid = ids[index]
        q = con.execute(
            """SELECT correct_answer FROM page_questions WHERE id=?
            UNION ALL SELECT correct_answer FROM final_questions WHERE id=? LIMIT 1""",
            (qid, qid)
        ).fetchone()
        if not q:
            return None
        correct = answer == q["correct_answer"]
        new_correct = session["correct_count"] + (1 if correct else 0)
        new_index = index + 1
        con.execute(
            "UPDATE quiz_sessions SET current_index=?,correct_count=? WHERE id=?",
            (new_index, new_correct, session_id)
        )
        if new_index < len(ids):
            return {
                "finished": False, "correct": correct, "next_question_id": ids[new_index],
                "number": new_index + 1, "total": len(ids)
            }
        total = len(ids)
        percent = round(new_correct / total * 100, 1) if total else 0
        con.execute(
            """INSERT INTO attempts
            (telegram_id,book_id,page_number,exam_type,percent,correct_count,total_count)
            VALUES(?,?,?,?,?,?,?)""",
            (user_id, session["book_id"], session["page_number"],
             session["quiz_type"], percent, new_correct, total)
        )
        con.execute("DELETE FROM quiz_sessions WHERE id=?", (session_id,))
        return {
            "finished": True, "correct": correct, "percent": percent,
            "correct_count": new_correct, "total": total,
            "passed": percent >= PASS_PERCENT, "quiz_type": session["quiz_type"],
            "book_id": session["book_id"], "page_number": session["page_number"]
        }
