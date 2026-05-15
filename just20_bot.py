"""
Just20 Telegram Bot v3 — PostgreSQL постоянная база данных
Рита говорит от первого лица
"""

import os
import json
import logging
import asyncio
import psycopg2
import psycopg2.extras
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
import httpx

# ══════════════════════════════════════════
# НАСТРОЙКИ
# ══════════════════════════════════════════
BOT_TOKEN = "8858775912:AAGrP1XCQAqdUUr0d7ffSR8esLwa3LRwRao"
YUKASSA_SHOP_ID = "ВАШ_SHOP_ID"
YUKASSA_SECRET_KEY = "ВАШ_SECRET_KEY"
ADMIN_ID = 8668453654
RITA_MUM_ID = 1335108148
SITE_URL = "https://just20.ru"
MOSCOW_TZ = pytz.timezone("Europe/Moscow")
PROMO_CODES = ["RITA2026", "JUST20TEST", "BETA2026"]

# ══════════════════════════════════════════
# POSTGRESQL DATABASE
# ══════════════════════════════════════════
def get_db():
    """Get database connection"""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL not set")
    return psycopg2.connect(db_url, sslmode='require')

def init_db():
    """Create tables and add permanent users"""
    conn = get_db()
    cur = conn.cursor()
    
    # Create users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            active BOOLEAN DEFAULT FALSE,
            tariff VARCHAR(50) DEFAULT 'basic',
            current_day INTEGER DEFAULT 1,
            start_date TIMESTAMP,
            last_morning DATE,
            last_lunch DATE,
            last_dinner DATE,
            waiting_payment BOOLEAN DEFAULT FALSE,
            username VARCHAR(255),
            full_name VARCHAR(255)
        )
    """)
    
    # Always ensure admin is active
    cur.execute("""
        INSERT INTO users (user_id, active, tariff, current_day, start_date)
        VALUES (%s, TRUE, 'premium', 1, NOW())
        ON CONFLICT (user_id) DO UPDATE SET active = TRUE, tariff = 'premium'
    """, (ADMIN_ID,))
    
    # Always ensure Rita's mum is active
    cur.execute("""
        INSERT INTO users (user_id, active, tariff, current_day, start_date)
        VALUES (%s, TRUE, 'full', 1, NOW())
        ON CONFLICT (user_id) DO UPDATE SET active = TRUE, tariff = 'full'
    """, (RITA_MUM_ID,))
    
    conn.commit()
    cur.close()
    conn.close()
    logging.info("✅ Database initialized!")

def get_user(user_id):
    """Get user from database"""
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        return dict(user) if user else None
    except Exception as e:
        logging.error(f"get_user error: {e}")
        return None

def save_user(user_id, data):
    """Save or update user in database"""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (user_id, active, tariff, current_day, start_date, 
                             last_morning, last_lunch, last_dinner, waiting_payment,
                             username, full_name)
            VALUES (%(user_id)s, %(active)s, %(tariff)s, %(current_day)s, %(start_date)s,
                   %(last_morning)s, %(last_lunch)s, %(last_dinner)s, %(waiting_payment)s,
                   %(username)s, %(full_name)s)
            ON CONFLICT (user_id) DO UPDATE SET
                active = EXCLUDED.active,
                tariff = EXCLUDED.tariff,
                current_day = EXCLUDED.current_day,
                last_morning = EXCLUDED.last_morning,
                last_lunch = EXCLUDED.last_lunch,
                last_dinner = EXCLUDED.last_dinner,
                waiting_payment = EXCLUDED.waiting_payment,
                username = EXCLUDED.username,
                full_name = EXCLUDED.full_name
        """, {
            'user_id': user_id,
            'active': data.get('active', False),
            'tariff': data.get('tariff', 'basic'),
            'current_day': data.get('current_day', 1),
            'start_date': data.get('start_date', datetime.now(MOSCOW_TZ)),
            'last_morning': data.get('last_morning'),
            'last_lunch': data.get('last_lunch'),
            'last_dinner': data.get('last_dinner'),
            'waiting_payment': data.get('waiting_payment', False),
            'username': data.get('username', ''),
            'full_name': data.get('full_name', ''),
        })
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logging.error(f"save_user error: {e}")

def activate_user(user_id, tariff="full", username="", full_name=""):
    """Activate user after payment"""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (user_id, active, tariff, current_day, start_date, 
                             waiting_payment, username, full_name)
            VALUES (%s, TRUE, %s, 1, NOW(), FALSE, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                active = TRUE, tariff = %s, waiting_payment = FALSE,
                username = %s, full_name = %s
        """, (user_id, tariff, username, full_name, tariff, username, full_name))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logging.error(f"activate_user error: {e}")

def get_all_active_users():
    """Get all active users for broadcasting"""
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM users WHERE active = TRUE AND current_day <= 21")
        users = [dict(u) for u in cur.fetchall()]
        cur.close()
        conn.close()
        return users
    except Exception as e:
        logging.error(f"get_all_active_users error: {e}")
        return []

def update_user_field(user_id, field, value):
    """Update single field for user"""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(f"UPDATE users SET {field} = %s WHERE user_id = %s", (value, user_id))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logging.error(f"update_user_field error: {e}")

# ══════════════════════════════════════════
# KEYBOARDS
# ══════════════════════════════════════════
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Перейти к занятию", callback_data="goto_exercise")],
        [
            InlineKeyboardButton("✅ Уже сделала!", callback_data="done"),
            InlineKeyboardButton("📅 Задание дня", callback_data="today"),
        ],
        [
            InlineKeyboardButton("🥗 Меню дня", callback_data="show_menu"),
            InlineKeyboardButton("📊 Мой прогресс", callback_data="show_progress"),
        ],
    ])

def payment_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Оформить доступ", url=f"{SITE_URL}/#pricing")],
        [InlineKeyboardButton("✅ У меня есть номер заказа", callback_data="check_payment")],
    ])

def checkin_keyboard(meal_type):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Поела!", callback_data=f"meal_done_{meal_type}"),
            InlineKeyboardButton("⏳ Скоро поем", callback_data=f"meal_soon_{meal_type}"),
        ],
        [InlineKeyboardButton("🎬 Перейти к занятию", callback_data="goto_exercise")],
    ])

def exercise_keyboard(day):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Открыть занятие", url=f"{SITE_URL}/members")],
        [
            InlineKeyboardButton("✅ Сделала занятие!", callback_data="done"),
            InlineKeyboardButton("⏳ Сделаю позже", callback_data="remind_later"),
        ],
    ])

# ══════════════════════════════════════════
# MESSAGES
# ══════════════════════════════════════════
MSG_WELCOME = """Привет! Это Рита! 🌸

Я так рада что ты здесь — ты уже сделала первый шаг к себе.

Just20 — это моя программа для занятых женщин. 20 минут в день, реальная еда, реальный результат — без наказаний и без стресса.

Чтобы начать — оформи доступ на сайте и возвращайся с номером заказа! 👇"""

MSG_ACCESS_GRANTED = """🎉 Добро пожаловать в Just20! Это Рита! 🌸

Я так рада тебя видеть! Ты приняла одно из лучших решений для себя.

Этот чат создан специально для таких женщин как ты — занятых, с семьёй, с работой, с реальной жизнью.

Вот что тебя ждёт каждый день:
🌅 В 9:00 — задание и меню на день
☀️ В 13:00 — чек-ин обеда
🌙 В 19:00 — чек-ин ужина

Используй кнопки ниже — они всегда здесь для тебя! 💕

Готова начать? 👇"""

# ══════════════════════════════════════════
# DAY DATA
# ══════════════════════════════════════════
DAYS = {
    1: {"title": "День 1 — Первый шаг! 🌟", "exercise": "Пробуждение тела — 15 минут", "breakfast": "Овсянка с черникой и мёдом — 365 ккал", "lunch": "Куриный суп с овощами — 320 ккал", "dinner": "Запечённый лосось с брокколи — 310 ккал", "snack": "Яблоко + грецкие орехи — 185 ккал", "total": "~1380 ккал"},
    2: {"title": "День 2 — Продолжаем! 💪", "exercise": "Динамика и тонус — 17 минут", "breakfast": "Яичница с помидорами и шпинатом — 380 ккал", "lunch": "Гречка с куриной грудкой — 430 ккал", "dinner": "Греческий салат с тунцом — 310 ккал", "snack": "Апельсин + миндаль — 185 ккал", "total": "~1305 ккал"},
    3: {"title": "День 3 — Три дня — уже привычка! 🌿", "exercise": "Гибкость и осанка — 15 минут", "breakfast": "Сырники со сметаной — 385 ккал", "lunch": "Борщ с фасолью — 325 ккал", "dinner": "Запечённое куриное филе — 305 ккал", "snack": "Груша с творогом — 205 ккал", "total": "~1220 ккал"},
    4: {"title": "День 4 — Движение и сила ⚡", "exercise": "Ноги и ягодицы — 20 минут", "breakfast": "Творожная запеканка с бананом — 385 ккал", "lunch": "Рис с куриной грудкой — 415 ккал", "dinner": "Салат с тунцом и авокадо — 330 ккал", "snack": "Яблоко с арахисовой пастой — 200 ккал", "total": "~1330 ккал"},
    5: {"title": "День 5 — Баланс 🌸", "exercise": "Баланс и координация — 15 минут", "breakfast": "Гречневые блины с творогом — 355 ккал", "lunch": "Чечевичный суп — 365 ккал", "dinner": "Треска на пару с брокколи — 285 ккал", "snack": "Апельсин с кефиром — 165 ккал", "total": "~1170 ккал"},
    6: {"title": "День 6 — Ты в ритме! 🔥", "exercise": "Руки и плечи — 18 минут", "breakfast": "Овсянка с яблоком и орехами — 390 ккал", "lunch": "Курица с картофелем — 430 ккал", "dinner": "Творожный салат с огурцом — 195 ккал", "snack": "Виноград + сыр — 200 ккал", "total": "~1215 ккал"},
    7: {"title": "День 7 — Неделя 1 завершена! 🎉", "exercise": "Восстановление и растяжка — 15 минут", "breakfast": "Йогурт с гранолой и малиной — 370 ккал", "lunch": "Куриный плов — 465 ккал", "dinner": "Семга с зелёным салатом — 375 ккал", "snack": "Запечённое яблоко с мёдом — 215 ккал", "total": "~1425 ккал"},
}
for d in range(8, 22):
    DAYS[d] = {"title": f"День {d} 🌸", "exercise": f"Занятие {d} — открой в личном кабинете", "breakfast": "Смотри в плане питания", "lunch": "Смотри в плане питания", "dinner": "Смотри в плане питания", "snack": "Смотри в плане питания", "total": "~1400–1600 ккал"}

def morning_message(day):
    d = DAYS.get(day, DAYS[1])
    return f"""🌅 Доброе утро! Это Рита 🌸

*{d['title']}*

🎬 *Занятие сегодня:*
{d['exercise']}

🥗 *Меню на день:*
☀️ Завтрак: {d['breakfast']}
🍎 Перекус: {d['snack']}
🍽️ Обед: {d['lunch']}
🌙 Ужин: {d['dinner']}

📊 Итого: {d['total']}
💧 Не забудь про 1.5–2 литра воды!

Начнём? 👇"""

# ══════════════════════════════════════════
# HANDLERS
# ══════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if user and user.get("active"):
        await update.message.reply_text(
            f"Привет! Это Рита 🌸\n\nРада видеть тебя снова! Чем могу помочь?",
            reply_markup=main_keyboard()
        )
    else:
        await update.message.reply_text(MSG_WELCOME, reply_markup=payment_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    text = update.message.text.strip()

    if user and user.get("waiting_payment"):
        # Check promo codes
        if text.upper() in PROMO_CODES:
            activate_user(user_id, "full",
                         update.effective_user.username or "",
                         update.effective_user.full_name or "")
            await update.message.reply_text(
                "🎁 Промо-код принят!\n\n" + MSG_ACCESS_GRANTED,
                reply_markup=main_keyboard()
            )
            try:
                await context.bot.send_message(ADMIN_ID,
                    f"🎁 Промо-код!\nID: {user_id}\nИмя: {update.effective_user.full_name}\nКод: {text.upper()}")
            except:
                pass
            return

        # Check YuKassa payment
        await update.message.reply_text("🔍 Проверяю твою оплату...")
        result = await check_yukassa_payment(text)
        if result.get("paid"):
            activate_user(user_id, "full",
                         update.effective_user.username or "",
                         update.effective_user.full_name or "")
            await update.message.reply_text(MSG_ACCESS_GRANTED, reply_markup=main_keyboard())
            try:
                await context.bot.send_message(ADMIN_ID,
                    f"✅ Новый покупатель!\nID: {user_id}\nИмя: {update.effective_user.full_name}")
            except:
                pass
        else:
            await update.message.reply_text(
                "Я не нашла этот номер заказа 🔍\n\nПроверь номер из письма после оплаты.\nЕсли у тебя есть промо-код — напиши его заглавными буквами.\nНапример: RITA2026 💕",
                reply_markup=payment_keyboard()
            )
        return

    if user and user.get("active"):
        if any(w in text.lower() for w in ["готово", "сделала", "готова"]):
            await process_done(update.message, user_id, context)
        else:
            await update.message.reply_text(
                "Я здесь! 🌸\n\nИспользуй кнопки ниже 💕",
                reply_markup=main_keyboard()
            )
    else:
        await update.message.reply_text(MSG_WELCOME, reply_markup=payment_keyboard())

async def process_done(msg, user_id, context):
    user = get_user(user_id)
    if not user or not user.get("active"):
        await msg.reply_text(MSG_WELCOME, reply_markup=payment_keyboard())
        return

    current_day = user.get("current_day", 1)
    new_day = current_day + 1
    days_done = current_day
    days_left = max(0, 21 - days_done)
    pct = min(100, int((days_done / 21) * 100))
    filled = int(pct / 10)
    bar = "🟣" * filled + "⬜" * (10 - filled)

    import random
    celebrations = ["ВОТ ЭТО ДА! 🎉🎉🎉", "УМНИЦА! Я в восторге! 🌟🌟🌟",
                   "ТЫ — ЗВЕЗДА! ⭐⭐⭐", "НЕВЕРОЯТНО! 🔥🔥🔥", "БРАВО! 💫💫💫"]
    messages = [
        "Ты только что сделала что-то важное для себя! 💪",
        "Знаешь что самое крутое? Ты не остановилась! 🌸",
        "Твоё тело говорит тебе спасибо! ✨",
        "Каждое занятие — инвестиция в себя! 💕",
    ]

    update_user_field(user_id, "current_day", new_day)

    if current_day >= 21:
        text = "🏆 ТЫ ПРОШЛА ВСЕ 21 ДЕНЬ! 🏆\n\nЭто невероятно! Ты доказала себе что можешь.\nЯ так тобой горжусь! 🌸💕"
    else:
        text = (f"{random.choice(celebrations)}\n\n"
                f"{random.choice(messages)}\n\n"
                f"{bar} {pct}%\n"
                f"День {current_day} ✅ выполнен!\n"
                f"Осталось: {days_left} дней\n\n"
                f"Завтра в 9:00 — День {new_day}. Я уже жду! 🌸")

    await msg.reply_text(text, reply_markup=main_keyboard())

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    data = query.data

    if data == "check_payment":
        if not user:
            save_user(user_id, {
                "active": False, "waiting_payment": True,
                "current_day": 1, "tariff": "none",
                "username": query.from_user.username or "",
                "full_name": query.from_user.full_name or "",
            })
        else:
            update_user_field(user_id, "waiting_payment", True)
        await query.message.reply_text(
            "Пришли мне номер заказа из письма после оплаты 💕\n\n"
            "Или напиши промо-код заглавными буквами."
        )

    elif data == "goto_exercise":
        if not user or not user.get("active"):
            await query.message.reply_text(MSG_WELCOME, reply_markup=payment_keyboard())
            return
        day = user.get("current_day", 1)
        d = DAYS.get(day, DAYS[1])
        await query.message.reply_text(
            f"🎬 *{d['title']}*\n\n*Занятие сегодня:*\n{d['exercise']}\n\nОткрой личный кабинет Just20 и включай видео!\n\nЯ жду твоего «Готово»! 💕🌸",
            parse_mode="Markdown",
            reply_markup=exercise_keyboard(day)
        )

    elif data == "today":
        if not user or not user.get("active"):
            await query.message.reply_text(MSG_WELCOME, reply_markup=payment_keyboard())
            return
        day = user.get("current_day", 1)
        await query.message.reply_text(
            morning_message(day),
            parse_mode="Markdown",
            reply_markup=exercise_keyboard(day)
        )

    elif data == "show_menu":
        if not user or not user.get("active"):
            await query.message.reply_text(MSG_WELCOME, reply_markup=payment_keyboard())
            return
        day = user.get("current_day", 1)
        d = DAYS.get(day, DAYS[1])
        await query.message.reply_text(
            f"🥗 *Меню — День {day}*\n\n"
            f"☀️ Завтрак: {d['breakfast']}\n"
            f"🍎 Перекус: {d['snack']}\n"
            f"🍽️ Обед: {d['lunch']}\n"
            f"🌙 Ужин: {d['dinner']}\n\n"
            f"📊 Итого: {d['total']}\n💧 Вода: 1.5–2 литра 🌸",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    elif data == "show_progress":
        if not user or not user.get("active"):
            await query.message.reply_text(MSG_WELCOME, reply_markup=payment_keyboard())
            return
        day = user.get("current_day", 1)
        done = day - 1
        left = max(0, 21 - done)
        pct = min(100, int((done / 21) * 100))
        bar = "🟣" * int(pct/10) + "⬜" * (10 - int(pct/10))
        await query.message.reply_text(
            f"📊 *Твой прогресс Just20* 🌸\n\n{bar} {pct}%\n\n"
            f"✅ Дней выполнено: {done}\n⏳ Дней осталось: {left}\n\n"
            f"{'🎉 Ты прошла программу!' if done >= 21 else 'Продолжай! Ты делаешь это! 💕'}\n\nРита 🌸",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    elif data == "done":
        if not user or not user.get("active"):
            await query.message.reply_text(MSG_WELCOME, reply_markup=payment_keyboard())
            return
        await process_done(query.message, user_id, context)

    elif data == "remind_later":
        await query.message.reply_text(
            "Хорошо! Напомню вечером 🌸\n\nВсего 20 минут — ты можешь! 💕",
            reply_markup=main_keyboard()
        )

    elif data.startswith("meal_done_"):
        meal_names = {"breakfast": "завтрак", "lunch": "обед", "dinner": "ужин"}
        meal = meal_names.get(data.replace("meal_done_", ""), "приём пищи")
        await query.message.reply_text(
            f"Отлично! Ты поела {meal} — молодец! 🌸\n\nРегулярное питание ускоряет метаболизм 💕",
            reply_markup=main_keyboard()
        )

    elif data.startswith("meal_soon_"):
        meal_names = {"breakfast": "завтракать", "lunch": "обедать", "dinner": "ужинать"}
        meal = meal_names.get(data.replace("meal_soon_", ""), "есть")
        await query.message.reply_text(
            f"Хорошо! Не забудь {meal} — это важно! 🌸💕",
            reply_markup=main_keyboard()
        )

# ══════════════════════════════════════════
# YUKASSA
# ══════════════════════════════════════════
async def check_yukassa_payment(payment_id: str) -> dict:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"https://api.yookassa.ru/v3/payments/{payment_id}",
                auth=(YUKASSA_SHOP_ID, YUKASSA_SECRET_KEY), timeout=10
            )
            if r.status_code == 200:
                data = r.json()
                return {"paid": data.get("status") == "succeeded"}
    except Exception as e:
        logging.error(f"YuKassa: {e}")
    return {"paid": False}

# ══════════════════════════════════════════
# BROADCASTS — Moscow time
# ══════════════════════════════════════════
async def morning_broadcast(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(MOSCOW_TZ).date()
    users = get_all_active_users()
    for user in users:
        if user.get("last_morning") == today:
            continue
        day = user.get("current_day", 1)
        try:
            await context.bot.send_message(
                user["user_id"], morning_message(day),
                parse_mode="Markdown",
                reply_markup=exercise_keyboard(day)
            )
            update_user_field(user["user_id"], "last_morning", today)
        except Exception as e:
            logging.error(f"Morning broadcast {user['user_id']}: {e}")

async def lunch_broadcast(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(MOSCOW_TZ).date()
    users = get_all_active_users()
    for user in users:
        if user.get("last_lunch") == today:
            continue
        day = user.get("current_day", 1)
        d = DAYS.get(day, DAYS[1])
        try:
            await context.bot.send_message(
                user["user_id"],
                f"☀️ Привет! Рита проверяет 🌸\n\nУже обеденное время!\n\n🍽️ *Обед сегодня:*\n{d['lunch']}\n\nТы уже поела? 👇",
                parse_mode="Markdown",
                reply_markup=checkin_keyboard("lunch")
            )
            update_user_field(user["user_id"], "last_lunch", today)
        except Exception as e:
            logging.error(f"Lunch broadcast {user['user_id']}: {e}")

async def dinner_broadcast(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(MOSCOW_TZ).date()
    users = get_all_active_users()
    for user in users:
        if user.get("last_dinner") == today:
            continue
        day = user.get("current_day", 1)
        d = DAYS.get(day, DAYS[1])
        try:
            await context.bot.send_message(
                user["user_id"],
                f"🌙 Добрый вечер! Рита на связи 🌸\n\nЗаканчиваем день вместе!\n\n🌙 *Ужин сегодня:*\n{d['dinner']}\n\nКак прошёл твой день? 👇",
                parse_mode="Markdown",
                reply_markup=checkin_keyboard("dinner")
            )
            update_user_field(user["user_id"], "last_dinner", today)
        except Exception as e:
            logging.error(f"Dinner broadcast {user['user_id']}: {e}")

# ══════════════════════════════════════════
# ADMIN
# ══════════════════════════════════════════
async def cmd_activate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Использование: /activate USER_ID")
        return
    target_id = int(context.args[0])
    activate_user(target_id)
    await update.message.reply_text(f"✅ Пользователь {target_id} активирован!")
    try:
        await context.bot.send_message(target_id, MSG_ACCESS_GRANTED, reply_markup=main_keyboard())
    except:
        pass

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users WHERE active = TRUE")
        active = cur.fetchone()[0]
        cur.close()
        conn.close()
        await update.message.reply_text(
            f"📊 Статистика Just20\n\nВсего: {total}\nАктивных: {active}"
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Привет! Это Рита* 🌸\n\nИспользуй кнопки ниже — они всегда здесь для тебя! 💕",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ══════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════
def main():
    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

    # Initialize database
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("activate", cmd_activate))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    import datetime as dt
    app.job_queue.run_daily(morning_broadcast, time=dt.time(9, 0, tzinfo=MOSCOW_TZ), name="morning")
    app.job_queue.run_daily(lunch_broadcast, time=dt.time(13, 0, tzinfo=MOSCOW_TZ), name="lunch")
    app.job_queue.run_daily(dinner_broadcast, time=dt.time(19, 0, tzinfo=MOSCOW_TZ), name="dinner")

    print("Just20 Bot v3 с PostgreSQL запущен! 🌸")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
