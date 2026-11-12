# -*- coding: utf-8 -*-
"""Imtihon Ustoz — imtihonga tayyorlov Telegram bot (kitob + test + audio + admin panel)."""
import os, re, io, csv, time, html, random, shutil, sqlite3, asyncio, threading
from datetime import datetime
from pathlib import Path

import telebot
from telebot.types import InlineKeyboardMarkup as KB, InlineKeyboardButton as Btn
from telebot.types import ReplyKeyboardMarkup

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ───────────── SOZLAMALAR ─────────────
TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.strip().isdigit()}
VOICE = os.getenv("TTS_VOICE", "uz-UZ-MadinaNeural")
DATA = Path(os.getenv("DATA_DIR", "data"))
PAGES, AUDIO, INBOX = DATA / "pages", DATA / "audio", Path("books_inbox")
for p in (DATA, PAGES, AUDIO, INBOX):
    p.mkdir(parents=True, exist_ok=True)

PASS_RATE = 0.7      # 70%
Q_PAGE = 4           # har varaq uchun savollar soni
Q_FINAL = 20         # kitob oxiridagi umumiy test savollari
DEFAULT_SUBJECTS = ["Matematika", "Fizika", "Kimyo", "Biologiya", "Ona tili", "Adabiyot",
                    "Tarix", "Geografiya", "Ingliz tili", "Huquq"]

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
esc = html.escape

# ───────────── BAZA ─────────────
db = sqlite3.connect(DATA / "bot.db", check_same_thread=False)
db.row_factory = sqlite3.Row
lock = threading.RLock()
db.executescript("""
CREATE TABLE IF NOT EXISTS users(tg_id INTEGER PRIMARY KEY, name TEXT, grade INTEGER, goal TEXT,
  subjects TEXT DEFAULT '', username TEXT, unlocked INTEGER DEFAULT 1, step TEXT DEFAULT 'name', joined TEXT);
CREATE TABLE IF NOT EXISTS books(id INTEGER PRIMARY KEY AUTOINCREMENT, grade INTEGER, subject TEXT, title TEXT, pages INTEGER);
CREATE TABLE IF NOT EXISTS pages(id INTEGER PRIMARY KEY AUTOINCREMENT, book_id INTEGER, num INTEGER, text TEXT, file_id TEXT);
CREATE TABLE IF NOT EXISTS progress(tg_id INTEGER, book_id INTEGER, cur INTEGER DEFAULT 1, done INTEGER DEFAULT 0, PRIMARY KEY(tg_id, book_id));
CREATE TABLE IF NOT EXISTS results(id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, book_id INTEGER, kind TEXT,
  page INTEGER, score INTEGER, total INTEGER, passed INTEGER, ts TEXT);
CREATE TABLE IF NOT EXISTS msgs(id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, text TEXT, ts TEXT);
""")
db.commit()


def q(sql, args=(), one=False):
    with lock:
        cur = db.execute(sql, args)
        return cur.fetchone() if one else cur.fetchall()


def ex(sql, args=()):
    with lock:
        cur = db.execute(sql, args)
        db.commit()
        return cur.lastrowid


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def get_user(uid):
    return q("SELECT * FROM users WHERE tg_id=?", (uid,), one=True)


def get_book(bid):
    return q("SELECT * FROM books WHERE id=?", (bid,), one=True)


def bar(n, total, w=10):
    f = round(w * n / max(total, 1))
    return "▓" * f + "░" * (w - f)


def subs_of(u):
    return [s for s in (u["subjects"] or "").split(",") if s]


def all_subjects():
    return sorted(set(DEFAULT_SUBJECTS) | {r["subject"] for r in q("SELECT DISTINCT subject FROM books")})


def show(c, text, kb=None):
    try:
        bot.edit_message_text(text, c.message.chat.id, c.message.message_id, reply_markup=kb)
    except Exception:
        bot.send_message(c.message.chat.id, text, reply_markup=kb)


# ───────────── TEST GENERATORI (kitob matnidan avtomatik) ─────────────
WORD = re.compile(r"[^\W\d_]{4,}(?:[ʻ'’`][^\W\d_]+)*", re.U)


def sentences(t):
    t = re.sub(r"\s+", " ", t or "")
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", t) if 40 <= len(s.strip()) <= 220]


def make_questions(texts, n):
    sents, words = [], set()
    for t in texts:
        sents += sentences(t)
        words.update(w.lower() for w in WORD.findall(t or ""))
    random.shuffle(sents)
    out = []
    for s in sents:
        cands = [w for w in WORD.findall(s) if len(w) >= 6]
        if not cands:
            continue
        ans = random.choice(cands)
        pool = [w for w in words if w != ans.lower() and abs(len(w) - len(ans)) <= 3]
        if len(pool) < 3:
            continue
        opts = random.sample(pool, 3) + [ans.lower()]
        random.shuffle(opts)
        out.append({"q": s.replace(ans, "_____", 1), "o": opts, "a": opts.index(ans.lower())})
        if len(out) >= n:
            break
    return out


# ───────────── PDF IMPORT (rasm + matn) ─────────────
def import_pdf(path, grade, subject, title, notify=None):
    import fitz  # PyMuPDF
    doc = fitz.open(str(path))
    bid = ex("INSERT INTO books(grade,subject,title,pages) VALUES(?,?,?,?)", (grade, subject, title, len(doc)))
    d = PAGES / str(bid)
    d.mkdir(parents=True, exist_ok=True)
    for i, pg in enumerate(doc, 1):
        pix = pg.get_pixmap(matrix=fitz.Matrix(1.4, 1.4))
        try:
            data = pix.tobytes("jpeg", jpg_quality=70)
        except TypeError:
            data = pix.tobytes("jpeg")
        (d / f"{i}.jpg").write_bytes(data)
        ex("INSERT INTO pages(book_id,num,text) VALUES(?,?,?)", (bid, i, pg.get_text()))
        if notify and i % 25 == 0:
            notify(f"⏳ {i}/{len(doc)} varaq tayyor...")
    doc.close()
    return bid


# ───────────── MENYU ─────────────
B_REC, B_ALL, B_RES, B_PROF = "📚 Tavsiya etilgan kitoblar", "🗂 Umumiy kitoblar", "📊 Natijalarim", "👤 Profil"


def menu(cid, text="🏠 Asosiy menyu"):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(B_REC, B_ALL, B_RES, B_PROF)
    bot.send_message(cid, text, reply_markup=kb)


def books_kb(uid, rows, back=None):
    u = get_user(uid)
    prog = {r["book_id"]: r for r in q("SELECT * FROM progress WHERE tg_id=?", (uid,))}
    kb = KB(row_width=1)
    for b in rows:
        p = prog.get(b["id"])
        icon = "🔒" if b["grade"] > u["unlocked"] else ("✅" if p and p["done"] else "📘")
        extra = f" • {p['cur']}/{b['pages']}" if p and not p["done"] else ""
        kb.add(Btn(f"{icon} {b['grade']}-sinf {b['subject']} — {b['title']}{extra}"[:60], callback_data=f"bk:{b['id']}"))
    if back:
        kb.add(Btn("⬅️ Orqaga", callback_data=back))
    return kb


def send_recommended(cid, uid):
    u = get_user(uid)
    rows = [b for b in q("SELECT * FROM books WHERE grade=? ORDER BY subject", (u["unlocked"],))
            if not subs_of(u) or b["subject"] in subs_of(u)]
    if not rows:
        return bot.send_message(cid, f"📭 {u['unlocked']}-sinf uchun tanlagan fanlaringizda hozircha kitob yo‘q.\n"
                                     "🗂 «Umumiy kitoblar» bo‘limini ko‘ring.")
    bot.send_message(cid, f"📚 <b>Sizga tavsiya:</b> {u['unlocked']}-sinf • {esc(', '.join(subs_of(u)) or 'barcha fanlar')}\n"
                          "Kitobni tanlang 👇", reply_markup=books_kb(uid, rows))


# ───────────── RO‘YXATDAN O‘TISH ─────────────
@bot.message_handler(commands=["start"])
def start(m):
    uid = m.from_user.id
    ex("INSERT OR IGNORE INTO users(tg_id,username,joined) VALUES(?,?,?)", (uid, m.from_user.username or "", now()))
    u = get_user(uid)
    if u["step"] == "done":
        return menu(m.chat.id, f"👋 Xush kelibsiz, <b>{esc(u['name'])}</b>!")
    bot.send_message(m.chat.id, "🎓 <b>Imtihon Ustoz</b> botiga xush kelibsiz!\n\n"
                                "Kitoblarni varaq-varaq o‘qing, har varaqdan test yeching va imtihonga tayyorlaning.\n"
                                "ℹ️ Ro‘yxatdan o‘tishda kiritilgan ma’lumotlar admin tomonidan ko‘rilishi mumkin.\n\n"
                                "✍️ Ismingiz va familiyangizni yozing:", reply_markup=telebot.types.ReplyKeyboardRemove())


def grade_kb():
    kb = KB(row_width=4)
    kb.add(*[Btn(f"{i}-sinf", callback_data=f"gr:{i}") for i in range(1, 12)])
    return kb


def subj_kb(sel):
    kb = KB(row_width=2)
    kb.add(*[Btn(("✅ " if s in sel else "▫️ ") + s, callback_data="sub:" + s) for s in all_subjects()])
    kb.add(Btn("➡️ Tayyor", callback_data="subok"))
    return kb


def reg_text(m, u):
    uid, t = m.from_user.id, m.text.strip()
    if not u:
        return start(m)
    if u["step"] == "name":
        ex("UPDATE users SET name=?,step='grade' WHERE tg_id=?", (t[:60], uid))
        bot.send_message(m.chat.id, "🏫 Nechanchi sinfda o‘qiysiz?", reply_markup=grade_kb())
    elif u["step"] == "goal":
        ex("UPDATE users SET goal=?,step='subjects',subjects='' WHERE tg_id=?", (t[:100], uid))
        bot.send_message(m.chat.id, "📘 Yo‘nalishingiz (blok) fanlarini belgilang (bir nechta tanlash mumkin):",
                         reply_markup=subj_kb([]))
    else:
        bot.send_message(m.chat.id, "👆 Iltimos, yuqoridagi tugmalardan foydalaning.")


# ───────────── SAHIFA KO‘RSATISH ─────────────
def page_passed(uid, bid, num):
    return q("SELECT 1 FROM results WHERE tg_id=? AND book_id=? AND kind='page' AND page=? AND passed=1",
             (uid, bid, num), one=True) is not None


def send_page(cid, uid, bid, num):
    b, pg = get_book(bid), q("SELECT * FROM pages WHERE book_id=? AND num=?", (bid, num), one=True)
    if not b or not pg:
        return bot.send_message(cid, "❌ Sahifa topilmadi.")
    kb = KB(row_width=2)
    kb.add(Btn("🔊 Audio", callback_data=f"au:{pg['id']}"), Btn("📄 Matn", callback_data=f"tx:{pg['id']}"))
    nav = []
    if num > 1:
        nav.append(Btn("⬅️ Oldingi", callback_data=f"pg:{bid}:{num-1}"))
    nav.append(Btn("➡️ Keyingi (test)" if num < b["pages"] else "🏁 Yakuniy test", callback_data=f"nx:{bid}:{num}"))
    kb.row(*nav)
    kb.add(Btn("📚 Kitoblar", callback_data="books"))
    cap = (f"📖 <b>{esc(b['title'])}</b>\n{b['grade']}-sinf • {esc(b['subject'])}\n"
           f"Varaq {num}/{b['pages']}  {bar(num, b['pages'])}")
    img = PAGES / str(bid) / f"{num}.jpg"
    if pg["file_id"]:
        try:
            return bot.send_photo(cid, pg["file_id"], caption=cap, reply_markup=kb)
        except Exception:
            pass
    if img.exists():
        with open(img, "rb") as f:
            msg = bot.send_photo(cid, f, caption=cap, reply_markup=kb)
        ex("UPDATE pages SET file_id=? WHERE id=?", (msg.photo[-1].file_id, pg["id"]))
    else:
        bot.send_message(cid, cap + "\n\n" + esc((pg["text"] or "")[:3000]), reply_markup=kb)


# ───────────── TEST ─────────────
QUIZ = {}


def render_q(cid, mid, st, new=False):
    i, qd = st["i"], st["qs"][st["i"]]
    kb = KB(row_width=1)
    for j, o in enumerate(qd["o"]):
        kb.add(Btn(o, callback_data=f"qz:{st['t']}:{j}"))
    text = (f"📝 <b>{esc(st['title'])}</b>\nSavol {i+1}/{len(st['qs'])}\n\n«{esc(qd['q'])}»\n\n"
            "✍️ Bo‘sh joyga mos so‘zni tanlang:")
    if new:
        bot.send_message(cid, text, reply_markup=kb)
    else:
        bot.edit_message_text(text, cid, mid, reply_markup=kb)


def start_quiz(cid, uid, kind, bid, page=None):
    b = get_book(bid)
    if kind == "page":
        texts = [r["text"] for r in q("SELECT text FROM pages WHERE book_id=? AND num=?", (bid, page), one=False)]
        pool = [r["text"] for r in q("SELECT text FROM pages WHERE book_id=? AND num BETWEEN ? AND ?",
                                     (bid, max(1, page - 3), page + 3))]
        qs = make_questions(texts + pool[:0], Q_PAGE)
        if len(qs) < Q_PAGE:   # savol yetmasa qo‘shni varaqlardan to‘ldiramiz
            qs += make_questions(pool, Q_PAGE - len(qs))
        title = f"{b['title']} • {page}-varaq testi"
    else:
        qs = make_questions([r["text"] for r in q("SELECT text FROM pages WHERE book_id=?", (bid,))], Q_FINAL)
        title = f"{b['title']} • YAKUNIY TEST"
    if not qs:
        if kind == "page":   # matn yo‘q (skaner) — test o‘tkazib yuboriladi
            ex("INSERT INTO results(tg_id,book_id,kind,page,score,total,passed,ts) VALUES(?,?,?,?,?,?,?,?)",
               (uid, bid, "page", page, 0, 0, 1, now()))
            ex("UPDATE progress SET cur=MAX(cur,?) WHERE tg_id=? AND book_id=?", (min(page + 1, b["pages"]), uid, bid))
            bot.send_message(cid, "ℹ️ Bu varaqda matn yo‘q, test o‘tkazib yuborildi.")
            return send_page(cid, uid, bid, min(page + 1, b["pages"]))
        return bot.send_message(cid, "ℹ️ Kitobda test tuzish uchun matn yetarli emas. Admin bilan bog‘laning.")
    st = {"kind": kind, "bid": bid, "page": page, "qs": qs, "i": 0, "ok": 0, "t": int(time.time()) % 100000, "title": title}
    QUIZ[uid] = st
    render_q(cid, None, st, new=True)


def check_unlock(uid, grade):
    u = get_user(uid)
    bks = q("SELECT id,subject FROM books WHERE grade=?", (grade,))
    need = [b["id"] for b in bks if not subs_of(u) or b["subject"] in subs_of(u)] or [b["id"] for b in bks]
    done = {r["book_id"] for r in q("SELECT book_id FROM progress WHERE tg_id=? AND done=1", (uid,))}
    if need and all(i in done for i in need) and grade == u["unlocked"] and grade < 11:
        ex("UPDATE users SET unlocked=? WHERE tg_id=?", (grade + 1, uid))
        return True
    return False


def finish_quiz(c, uid, st):
    bid, total, ok = st["bid"], len(st["qs"]), st["ok"]
    b = get_book(bid)
    passed = ok / total >= PASS_RATE
    ex("INSERT INTO results(tg_id,book_id,kind,page,score,total,passed,ts) VALUES(?,?,?,?,?,?,?,?)",
       (uid, bid, st["kind"], st["page"], ok, total, int(passed), now()))
    pct = round(100 * ok / total)
    head = f"{'🎉' if passed else '😕'} <b>Natija: {ok}/{total} ({pct}%)</b>\n"
    kb = KB(row_width=1)
    if st["kind"] == "page":
        n = st["page"]
        if passed:
            if n < b["pages"]:
                ex("UPDATE progress SET cur=MAX(cur,?) WHERE tg_id=? AND book_id=?", (n + 1, uid, bid))
                text = head + "✅ Test topshirildi! Keyingi varaqqa o‘tishingiz mumkin."
                kb.add(Btn("➡️ Keyingi varaq", callback_data=f"pg:{bid}:{n+1}"))
            else:
                text = head + "✅ Oxirgi varaq tugadi! Endi kitob bo‘yicha yakuniy test."
                kb.add(Btn("🏁 Yakuniy testni boshlash", callback_data=f"fq:{bid}"))
        else:
            text = head + f"❌ O‘tish uchun kamida {int(PASS_RATE*100)}% kerak. Varaqni qayta o‘qing."
            kb.add(Btn("📖 Qayta o‘qish", callback_data=f"pg:{bid}:{n}"), Btn("🔄 Testni qayta yechish", callback_data=f"qs:{bid}:{n}"))
    else:
        if passed:
            ex("UPDATE progress SET done=1 WHERE tg_id=? AND book_id=?", (uid, bid))
            text = head + f"🏆 «{esc(b['title'])}» kitobi tugatildi!"
            if check_unlock(uid, b["grade"]):
                text += f"\n\n🔓 {b['grade']+1}-sinf kitoblari ochildi!"
            kb.add(Btn("📚 Kitoblar", callback_data="books"))
        else:
            text = head + f"❌ Yakuniy testdan o‘tish uchun {int(PASS_RATE*100)}% kerak."
            kb.add(Btn("🔄 Qayta urinish", callback_data=f"fq:{bid}"), Btn("📖 Kitobni takrorlash", callback_data=f"pg:{bid}:1"))
    QUIZ.pop(uid, None)
    show(c, text, kb)


# ───────────── AUDIO ─────────────
def tts(text, path):
    import edge_tts

    async def run():
        await edge_tts.Communicate(text, VOICE).save(str(path))
    asyncio.run(run())


def send_audio(cid, pid):
    pg = q("SELECT * FROM pages WHERE id=?", (pid,), one=True)
    text = re.sub(r"\s+", " ", pg["text"] or "").strip()[:2500]
    if not text:
        return bot.send_message(cid, "ℹ️ Bu varaqda o‘qiladigan matn yo‘q.")
    f = AUDIO / f"{pid}.mp3"
    if not f.exists():
        wait = bot.send_message(cid, "⏳ Audio tayyorlanmoqda...")
        try:
            tts(text, f)
        except Exception as e:
            return bot.edit_message_text(f"❌ Audio yaratib bo‘lmadi: {esc(str(e)[:150])}", cid, wait.message_id)
        bot.delete_message(cid, wait.message_id)
    with open(f, "rb") as fh:
        bot.send_audio(cid, fh, title=f"{pg['num']}-varaq")


# ───────────── ADMIN PANEL ─────────────
ADM = {}


def admin_kb():
    kb = KB(row_width=2)
    kb.add(Btn("📊 Statistika", callback_data="ad:stat"), Btn("👥 Foydalanuvchilar", callback_data="ad:users:0"),
           Btn("📥 Kitob qo‘shish (PDF)", callback_data="ad:add"), Btn("📂 Papkadan import", callback_data="ad:inbox"),
           Btn("📢 Xabar yuborish", callback_data="ad:bc"), Btn("📄 CSV eksport", callback_data="ad:csv"),
           Btn("🗑 Kitob o‘chirish", callback_data="ad:del"))
    return kb


@bot.message_handler(commands=["admin"])
def admin_cmd(m):
    if m.from_user.id not in ADMIN_IDS:
        return
    ADM.pop(m.from_user.id, None)
    bot.send_message(m.chat.id, "🛠 <b>Admin panel</b>", reply_markup=admin_kb())


@bot.message_handler(commands=["cancel"])
def cancel(m):
    ADM.pop(m.from_user.id, None)
    bot.send_message(m.chat.id, "Bekor qilindi.")


def user_card(tg):
    u = get_user(tg)
    if not u:
        return "Topilmadi"
    prog = q("SELECT p.*, b.title, b.pages FROM progress p JOIN books b ON b.id=p.book_id WHERE p.tg_id=?", (tg,))
    res = q("SELECT COUNT(*) n, SUM(passed) ps FROM results WHERE tg_id=?", (tg,), one=True)
    msgs = q("SELECT text, ts FROM msgs WHERE tg_id=? ORDER BY id DESC LIMIT 10", (tg,))
    t = (f"👤 <b>{esc(u['name'] or '—')}</b>\n🆔 <a href='tg://user?id={tg}'>{tg}</a>  @{esc(u['username'] or '—')}\n"
         f"🏫 Sinf: {u['grade']} (ochiq: {u['unlocked']}-sinf)\n🎓 Maqsad: {esc(u['goal'] or '—')}\n"
         f"📘 Fanlar: {esc(u['subjects'] or '—')}\n📅 Qo‘shilgan: {u['joined']}\n"
         f"🧪 Testlar: {res['n'] or 0} ta, o‘tgan: {res['ps'] or 0}\n\n<b>Kitoblar:</b>\n")
    t += "\n".join(f"• {esc(p['title'])}: {p['cur']}/{p['pages']} {'✅' if p['done'] else ''}" for p in prog) or "—"
    t += "\n\n<b>So‘nggi xabarlari:</b>\n" + ("\n".join(f"[{x['ts']}] {esc(x['text'][:100])}" for x in msgs) or "—")
    return t[:4000]


def bg(fn, *a):
    threading.Thread(target=fn, args=a, daemon=True).start()


def do_inbox(cid):
    files = sorted(INBOX.glob("*.pdf"))
    if not files:
        return bot.send_message(cid, "📂 <code>books_inbox/</code> papkasi bo‘sh.\nFayl nomi: <code>5-sinf__Matematika__Algebra.pdf</code>")
    for f in files:
        try:
            parts = f.stem.split("__")
            g = int(re.search(r"\d+", parts[0]).group())
            bot.send_message(cid, f"⏳ Import: {esc(f.name)}")
            import_pdf(f, g, parts[1].strip(), parts[2].strip() if len(parts) > 2 else parts[1].strip())
            f.rename(f.with_suffix(".done"))
            bot.send_message(cid, f"✅ Tayyor: {esc(f.stem)}")
        except Exception as e:
            bot.send_message(cid, f"❌ {esc(f.name)}: {esc(str(e)[:200])}")


def do_broadcast(cid, text):
    ok = 0
    for r in q("SELECT tg_id FROM users WHERE step='done'"):
        try:
            bot.send_message(r["tg_id"], "📢 " + esc(text))
            ok += 1
        except Exception:
            pass
        time.sleep(0.05)
    bot.send_message(cid, f"✅ {ok} ta foydalanuvchiga yuborildi.")


def handle_admin_text(m, st):
    uid, t = m.from_user.id, m.text.strip()
    if st["act"] == "meta":
        try:
            g, s, ti = [x.strip() for x in t.split("|")]
            ADM[uid] = {"act": "pdf", "meta": (int(g), s, ti)}
            bot.send_message(m.chat.id, "📎 Endi PDF faylni yuboring (20 MB gacha; kattasi uchun «Papkadan import»).")
        except Exception:
            bot.send_message(m.chat.id, "Format: <code>5|Matematika|Algebra 5-sinf</code>")
        return True
    if st["act"] == "bc":
        ADM.pop(uid)
        bg(do_broadcast, m.chat.id, t)
        return True
    if st["act"] == "dm":
        ADM.pop(uid)
        try:
            bot.send_message(st["to"], "✉️ <b>Admindan xabar:</b>\n" + esc(t))
            bot.send_message(m.chat.id, "✅ Yuborildi.")
        except Exception as e:
            bot.send_message(m.chat.id, f"❌ {esc(str(e)[:100])}")
        return True
    return False


@bot.message_handler(content_types=["document"])
def on_doc(m):
    uid = m.from_user.id
    st = ADM.get(uid)
    if uid not in ADMIN_IDS or not st or st["act"] != "pdf":
        return
    if not (m.document.file_name or "").lower().endswith(".pdf"):
        return bot.send_message(m.chat.id, "Faqat PDF yuboring.")
    g, s, ti = st["meta"]
    ADM.pop(uid)

    def work():
        try:
            bot.send_message(m.chat.id, "⏳ Yuklanmoqda va varaqlarga bo‘linmoqda...")
            data = bot.download_file(bot.get_file(m.document.file_id).file_path)
            tmp = INBOX / f"_tmp_{int(time.time())}.pdf"
            tmp.write_bytes(data)
            bid = import_pdf(tmp, g, s, ti, notify=lambda x: bot.send_message(m.chat.id, x))
            tmp.unlink(missing_ok=True)
            bot.send_message(m.chat.id, f"✅ Kitob qo‘shildi (ID {bid}): {g}-sinf • {esc(s)} • {esc(ti)}")
        except Exception as e:
            bot.send_message(m.chat.id, f"❌ Xato: {esc(str(e)[:250])}\nKatta fayl bo‘lsa «Papkadan import»dan foydalaning.")
    bg(work)


def admin_cb(c, a):
    uid, cid = c.from_user.id, c.message.chat.id
    k = a[1]
    if k == "home":
        show(c, "🛠 <b>Admin panel</b>", admin_kb())
    elif k == "stat":
        n = q("SELECT COUNT(*) n FROM users WHERE step='done'", one=True)["n"]
        today = q("SELECT COUNT(*) n FROM users WHERE joined LIKE ?", (datetime.now().strftime("%Y-%m-%d") + "%",), one=True)["n"]
        bk = q("SELECT COUNT(*) n, COALESCE(SUM(pages),0) p FROM books", one=True)
        r = q("SELECT COUNT(*) n, COALESCE(SUM(passed),0) p FROM results", one=True)
        show(c, f"📊 <b>Statistika</b>\n👥 Foydalanuvchilar: {n} (bugun +{today})\n📚 Kitoblar: {bk['n']} ({bk['p']} varaq)\n"
                f"🧪 Testlar: {r['n']} (o‘tgan: {r['p']})", KB().add(Btn("⬅️", callback_data="ad:home")))
    elif k == "users":
        off = int(a[2])
        rows = q("SELECT * FROM users WHERE step='done' ORDER BY joined DESC LIMIT 8 OFFSET ?", (off,))
        kb = KB(row_width=1)
        for u in rows:
            kb.add(Btn(f"👤 {u['name']} • {u['grade']}-sinf", callback_data=f"ad:u:{u['tg_id']}"))
        nav = []
        if off:
            nav.append(Btn("◀️", callback_data=f"ad:users:{max(0, off-8)}"))
        if len(rows) == 8:
            nav.append(Btn("▶️", callback_data=f"ad:users:{off+8}"))
        if nav:
            kb.row(*nav)
        kb.add(Btn("⬅️ Admin", callback_data="ad:home"))
        show(c, "👥 <b>Foydalanuvchilar</b>", kb)
    elif k == "u":
        kb = KB(row_width=1).add(Btn("✉️ Xabar yozish", callback_data=f"ad:dm:{a[2]}"), Btn("⬅️ Ro‘yxat", callback_data="ad:users:0"))
        show(c, user_card(int(a[2])), kb)
    elif k == "dm":
        ADM[uid] = {"act": "dm", "to": int(a[2])}
        bot.send_message(cid, "✍️ Xabar matnini yozing (/cancel — bekor):")
    elif k == "add":
        ADM[uid] = {"act": "meta"}
        bot.send_message(cid, "📘 Kitob ma’lumoti: <code>sinf|fan|nomi</code>\nMasalan: <code>5|Matematika|Algebra 5-sinf</code>")
    elif k == "inbox":
        bg(do_inbox, cid)
    elif k == "bc":
        ADM[uid] = {"act": "bc"}
        bot.send_message(cid, "📢 Hammaga yuboriladigan xabarni yozing (/cancel — bekor):")
    elif k == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["tg_id", "username", "ism", "sinf", "maqsad", "fanlar", "ochiq_sinf", "qoshilgan"])
        for u in q("SELECT * FROM users WHERE step='done'"):
            w.writerow([u["tg_id"], u["username"], u["name"], u["grade"], u["goal"], u["subjects"], u["unlocked"], u["joined"]])
        f = io.BytesIO(buf.getvalue().encode("utf-8-sig"))
        f.name = "foydalanuvchilar.csv"
        bot.send_document(cid, f)
    elif k == "del":
        kb = KB(row_width=1)
        for b in q("SELECT * FROM books ORDER BY grade"):
            kb.add(Btn(f"🗑 {b['grade']}-sinf {b['subject']} — {b['title']}"[:60], callback_data=f"ad:dl:{b['id']}"))
        kb.add(Btn("⬅️", callback_data="ad:home"))
        show(c, "Qaysi kitob o‘chirilsin?", kb)
    elif k == "dl":
        show(c, "⚠️ Rostdan o‘chirilsinmi?", KB().add(Btn("✅ Ha", callback_data=f"ad:dy:{a[2]}"), Btn("❌ Yo‘q", callback_data="ad:del")))
    elif k == "dy":
        bid = int(a[2])
        for t in ("pages", "progress", "results"):
            ex(f"DELETE FROM {t} WHERE book_id=?", (bid,))
        ex("DELETE FROM books WHERE id=?", (bid,))
        shutil.rmtree(PAGES / str(bid), ignore_errors=True)
        show(c, "✅ O‘chirildi.", KB().add(Btn("⬅️ Admin", callback_data="ad:home")))


# ───────────── MATNLI XABARLAR ─────────────
@bot.message_handler(content_types=["text"])
def on_text(m):
    uid, t = m.from_user.id, m.text.strip()
    if t.startswith("/"):
        return
    ex("INSERT INTO msgs(tg_id,text,ts) VALUES(?,?,?)", (uid, t[:500], now()))
    st = ADM.get(uid)
    if st and uid in ADMIN_IDS and handle_admin_text(m, st):
        return
    u = get_user(uid)
    if not u or u["step"] != "done":
        return reg_text(m, u)
    if t == B_REC:
        send_recommended(m.chat.id, uid)
    elif t == B_ALL:
        kb = KB(row_width=4)
        kb.add(*[Btn(f"{i}-sinf", callback_data=f"gp:{i}") for i in range(1, 12)])
        bot.send_message(m.chat.id, "🗂 <b>Umumiy kitoblar</b>\nSinfni tanlang:", reply_markup=kb)
    elif t == B_RES:
        rows = q("SELECT p.*, b.title, b.pages, b.grade FROM progress p JOIN books b ON b.id=p.book_id WHERE p.tg_id=?", (uid,))
        r = q("SELECT COUNT(*) n, COALESCE(SUM(passed),0) p, COALESCE(SUM(score),0) s, COALESCE(SUM(total),0) t FROM results WHERE tg_id=?", (uid,), one=True)
        txt = "📊 <b>Natijalarim</b>\n\n" + ("\n".join(
            f"{'✅' if x['done'] else '📖'} {esc(x['title'])}\n   {bar(x['cur'], x['pages'])} {x['cur']}/{x['pages']}" for x in rows) or "Hali kitob boshlanmagan.")
        if r["n"]:
            txt += f"\n\n🧪 Testlar: {r['n']} • o‘tgan: {r['p']} • o‘rtacha: {round(100*r['s']/max(r['t'],1))}%"
        bot.send_message(m.chat.id, txt)
    elif t == B_PROF:
        kb = KB().add(Btn("✏️ Ma’lumotlarni o‘zgartirish", callback_data="rereg"))
        bot.send_message(m.chat.id, f"👤 <b>{esc(u['name'])}</b>\n🏫 {u['grade']}-sinf (ochiq: {u['unlocked']}-sinf)\n"
                                    f"🎓 {esc(u['goal'])}\n📘 {esc(u['subjects'])}", reply_markup=kb)
    else:
        bot.send_message(m.chat.id, "Menyudagi tugmalardan foydalaning 👇")


# ───────────── CALLBACKLAR ─────────────
@bot.callback_query_handler(func=lambda c: True)
def on_cb(c):
    uid, cid = c.from_user.id, c.message.chat.id
    a = c.data.split(":", 2) if c.data.startswith("sub:") else c.data.split(":")
    k, toast, alert = a[0], None, False
    try:
        u = get_user(uid)
        if k == "ad":
            if uid in ADMIN_IDS:
                admin_cb(c, a)
        elif not u:
            toast = "Avval /start bosing"
        elif k == "gr":
            ex("UPDATE users SET grade=?,unlocked=?,step='goal' WHERE tg_id=?", (int(a[1]), int(a[1]), uid))
            show(c, "🎓 Qaysi oliy o‘quv yurtiga / yo‘nalishga kirmoqchisiz? Yozib yuboring:")
        elif k == "sub":
            sel = subs_of(u)
            sel.remove(a[1]) if a[1] in sel else sel.append(a[1])
            ex("UPDATE users SET subjects=? WHERE tg_id=?", (",".join(sel), uid))
            bot.edit_message_reply_markup(cid, c.message.message_id, reply_markup=subj_kb(sel))
        elif k == "subok":
            if not subs_of(u):
                toast, alert = "Kamida bitta fan tanlang", True
            else:
                ex("UPDATE users SET step='done' WHERE tg_id=?", (uid,))
                show(c, "✅ Ro‘yxatdan o‘tdingiz!")
                menu(cid, "🎉 Tayyor! Sizga mos kitoblar:")
                send_recommended(cid, uid)
        elif k == "rereg":
            ex("UPDATE users SET step='name' WHERE tg_id=?", (uid,))
            bot.send_message(cid, "✍️ Ismingizni yozing:", reply_markup=telebot.types.ReplyKeyboardRemove())
        elif k == "books":
            send_recommended(cid, uid)
        elif k == "gp":
            g = int(a[1])
            rows = q("SELECT * FROM books WHERE grade=? ORDER BY subject", (g,))
            if not rows:
                toast, alert = f"{g}-sinf uchun kitob hali yo‘q", True
            else:
                show(c, f"🗂 <b>{g}-sinf kitoblari</b>", books_kb(uid, rows))
        elif k == "bk":
            b = get_book(int(a[1]))
            if b["grade"] > u["unlocked"]:
                toast, alert = f"🔒 Avval {u['unlocked']}-sinf kitoblarini tugating", True
            else:
                ex("INSERT OR IGNORE INTO progress(tg_id,book_id) VALUES(?,?)", (uid, b["id"]))
                p = q("SELECT cur FROM progress WHERE tg_id=? AND book_id=?", (uid, b["id"]), one=True)
                send_page(cid, uid, b["id"], p["cur"])
        elif k == "pg":
            bid, num = int(a[1]), int(a[2])
            p = q("SELECT cur FROM progress WHERE tg_id=? AND book_id=?", (uid, bid), one=True)
            if not p or num > p["cur"]:
                toast, alert = "Avval oldingi varaq testidan o‘ting", True
            else:
                try: bot.delete_message(cid, c.message.message_id)
                except Exception: pass
                send_page(cid, uid, bid, num)
        elif k == "nx":
            bid, num = int(a[1]), int(a[2])
            b = get_book(bid)
            try: bot.delete_message(cid, c.message.message_id)
            except Exception: pass
            if page_passed(uid, bid, num):
                send_page(cid, uid, bid, num + 1) if num < b["pages"] else start_quiz(cid, uid, "final", bid)
            else:
                start_quiz(cid, uid, "page", bid, num)
        elif k == "qs":
            start_quiz(cid, uid, "page", int(a[1]), int(a[2]))
        elif k == "fq":
            start_quiz(cid, uid, "final", int(a[1]))
        elif k == "qz":
            st = QUIZ.get(uid)
            if not st or str(st["t"]) != a[1]:
                toast, alert = "Test eskirgan, qaytadan boshlang", True
            else:
                qd = st["qs"][st["i"]]
                j = int(a[2])
                if j == qd["a"]:
                    st["ok"] += 1
                    toast = "✅ To‘g‘ri!"
                else:
                    toast = f"❌ Noto‘g‘ri. To‘g‘ri javob: {qd['o'][qd['a']]}"
                st["i"] += 1
                if st["i"] >= len(st["qs"]):
                    finish_quiz(c, uid, st)
                else:
                    render_q(cid, c.message.message_id, st)
        elif k == "au":
            bg(send_audio, cid, int(a[1]))
        elif k == "tx":
            pg = q("SELECT text FROM pages WHERE id=?", (int(a[1]),), one=True)
            t = re.sub(r"\n{3,}", "\n\n", (pg["text"] or "").strip())
            bot.send_message(cid, esc(t[:3800]) if t else "ℹ️ Bu varaqda matn yo‘q.")
    except Exception as e:
        print("CB xato:", repr(e))
    try:
        bot.answer_callback_query(c.id, toast, show_alert=alert)
    except Exception:
        pass


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi! .env faylga yozing.")
    print("Bot ishga tushdi...")
    bot.infinity_polling(skip_pending=True, timeout=30)
