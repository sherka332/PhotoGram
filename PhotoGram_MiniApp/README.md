# PhotoGram Telegram Mini App

## Ishga tushirish
```bash
pip install -r requirements.txt
python app.py
```

## Admin qilish
`.env` fayl yarating va:
```env
SECRET_KEY=uzun-maxfiy-kalit
ADMIN_ID=YOUR_TELEGRAM_NUMERIC_ID
```

## Render
Build Command:
`pip install -r requirements.txt`

Start Command:
`gunicorn app:app`

## Muhim
1. Render local diskidagi `static/uploads` doimiy storage emas. Production uchun Cloudinary yoki Supabase Storage qo'shish tavsiya qilinadi.
2. `/api/login` hozir development uchun soddalashtirilgan. Productionga chiqarishdan oldin Telegram `initData` server-side HMAC tekshiruvini qo'shing.
3. Platformada report/moderatsiya funksiyasi bor. Admin nomaqbul postlarni yashirishi yoki o'chirishi mumkin.
