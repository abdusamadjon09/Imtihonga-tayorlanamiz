# IMTIHON USTOZ — Telegram bot

O‘zbekiston oliy ta’lim muassasalariga kirish imtihonlariga tayyorlanish uchun Telegram ta’lim boti.

## Loyihada bor
- Ism-familiya, sinf, oliygoh, yo‘nalish va fanlar bo‘yicha ro‘yxatdan o‘tish.
- 1–11-sinf kutubxonasi: admin kitoblarni sinf/fan bo‘yicha qo‘shadi.
- Sahifa matni, rasm va audio faylini Telegram orqali admin yuklaydi.
- Har bir sahifaga test savollari.
- Sahifa testida 70% va undan yuqori natija bilan keyingi sahifa ochiladi.
- Kitobning oxirgi sahifasidan so‘ng yakuniy imtihon.
- Yakuniy imtihonda 70% bilan kitob tugallangan deb belgilanadi.
- O‘quvchi profili va natijalar statistikasi.
- Faqat `ADMIN_ID` egasi uchun admin panel.

## Muhim kontent eslatmasi
Barcha sinflarning barcha darsliklari ushbu kod ichiga avtomatik joylanmagan. Kitoblar va sahifalar kontentidir; ularni rasmiy ochiq manbalardan yoki tarqatishga ruxsat olingan materiallardan admin yuklashi kerak. Mualliflik huquqi bilan himoyalangan kitoblarni ruxsatsiz tarqatmang. Kirish imtihoni savollari ham rasmiy testlar bilan bir xil deb kafolatlanmaydi; rasmiy namunalar va o‘quv dasturiga mos kontentdan foydalaning.

## 1. Bot tokeni
Telegram'da `@BotFather` → `/newbot` orqali bot yarating. Tokenni maxfiy saqlang. Uni GitHub'ga joylamang.

## 2. Admin Telegram ID
Telegram numeric ID raqamingizni aniqlang. Render'da `ADMIN_ID` environment variable sifatida kiriting. Bot paneliga `/admin` buyrug‘i bilan kirasiz.

## 3. GitHub
1. GitHub'da `imtihon-ustoz` nomli repository oching.
2. ZIP ichidagi `IMTIHON_USTOZ_GITHUB` papkasining ichidagi barcha fayl va papkalarni repository root'iga yuklang.
3. `.env` va `.db` fayllarini yuklamang.

## 4. Render
Tavsiya: Render Blueprint orqali `render.yaml` ni aniqlating yoki Web Service yarating.

- Build: `pip install -r requirements.txt`
- Start: `gunicorn --workers 1 --threads 4 app:web`
- Environment:
  - `BOT_TOKEN` = BotFather tokeni
  - `ADMIN_ID` = sizning Telegram numeric ID raqamingiz
  - `DATABASE_PATH` = `/var/data/imtihon_ustoz.db`

`render.yaml` persistent diskni Starter rejasida ulash uchun sozlangan. Bepul rejada doimiy disk bo‘lmasligi mumkin; SQLite ma’lumotlari deploy/restartda yo‘qolishi ehtimoli bor. Ishlab turgan xizmat uchun persistent disk yoki PostgreSQL ishlating. Bitta Gunicorn worker ishlating, chunki bot polling shu jarayonda ishga tushadi.

## 5. Admin paneldan kontent kiritish
Botda `/admin` yuboring.

### Kitob qo‘shish
Admin panel → Kitob qo‘shish. Format:
`SINF|FAN|KITOB NOMI|IZOH`

Masalan:
`11|Matematika|Algebra asoslari|11-sinf uchun darslik`

Keyin Admin panel → Kitoblar ro‘yxati orqali kitob ID sini ko‘ring.

### Sahifa qo‘shish
Admin panel → Sahifa qo‘shish. Format:
`KITOB_ID|SAHIFA_RAQAMI|SAHIFA NOMI|SAHIFA MATNI`

Masalan:
`1|1|Chiziqli tenglamalar|ax+b=0 ko‘rinishidagi tenglama chiziqli tenglama deyiladi.`

Keyin bot so‘raganda sahifa rasmini yuboring yoki `/skipphoto`; so‘ng audio yuboring yoki `/skipaudio`.

### Sahifa testi savoli
Avval sahifa ID sini bot sahifa qo‘shilganda ko‘rsatadi.
Format:
`SAHIFA_ID|SAVOL|A_VARIANT|B_VARIANT|C_VARIANT|D_VARIANT|TO‘G‘RI_HARF`

Masalan:
`1|2+2 nechaga teng?|3|4|5|6|B`

Bir sahifaga bir nechta savol kiriting. Barcha kiritilgan savollardan test tuziladi.

### Kitob yakuniy imtihoni
Format:
`KITOB_ID|SAVOL|A_VARIANT|B_VARIANT|C_VARIANT|D_VARIANT|TO‘G‘RI_HARF`

Kitobda yakuniy imtihon uchun savollar bo‘lishi shart.

## 6. O‘quvchi yo‘riqnomasi
`/start` → ro‘yxatdan o‘tish → “Mening fanlarim” yoki “Barcha kitoblar” → kitob → sahifa → test. Audio uchun “Audio tinglash” tugmasi bor.

## 7. Hozirgi versiya chegaralari
- Har bir sahifaga kiritilgan barcha savollar testda ishlatiladi.
- Yakuniy imtihon savollari kitob bo‘yicha alohida saqlanadi.
- Kitoblar ketma-ketligi va sinfdan sinfga avtomatik ko‘tarish hozircha qo‘lda boshqariladi.
- Sertifikat, to‘lov, AI ustoz va murakkab analitika kiritilmagan.
- Rasm/audio Telegram file_id orqali saqlanadi; faylning o‘zi bot serveriga ko‘chirilmaydi.

## 8. Xavfsizlik
- Token va admin ID ni GitHub kodiga yozmang.
- Admin panel faqat `ADMIN_ID` bilan himoyalangan.
- O‘quvchilarning shaxsiy ma’lumotlarini faqat xizmat ko‘rsatish uchun ishlating; admin ma’lumotlariga kirishni cheklang.
