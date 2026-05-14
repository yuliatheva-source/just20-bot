"""
Just20 Telegram Bot v2 — Полная версия с чек-инами и кнопками
Рита говорит от первого лица
Доступ только после проверки оплаты через YuKassa
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
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
SITE_URL = "https://just20.ru"
MOSCOW_TZ = pytz.timezone("Europe/Moscow")

DB_FILE = "users.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def get_user(user_id):
    return load_db().get(str(user_id))

def save_user(user_id, data):
    db = load_db()
    db[str(user_id)] = data
    save_db(db)

def activate_user(user_id, tariff="full"):
    user = get_user(user_id) or {}
    user.update({
        "active": True,
        "tariff": tariff,
        "start_date": datetime.now(MOSCOW_TZ).isoformat(),
        "current_day": 1,
        "last_morning": None,
        "last_lunch": None,
        "last_dinner": None,
    })
    save_user(user_id, user)

# ══════════════════════════════════════════
# КНОПКИ
# ══════════════════════════════════════════
def main_keyboard():
    """Главная клавиатура — всегда внизу"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Перейти к занятию", callback_data="goto_exercise")],
        [
            InlineKeyboardButton("✅ Уже сделала!", callback_data="done"),
            InlineKeyboardButton("📅 Моё задание", callback_data="today"),
        ],
        [
            InlineKeyboardButton("🥗 Меню дня", callback_data="show_menu"),
            InlineKeyboardButton("📊 Мой прогресс", callback_data="show_progress"),
        ],
    ])

def checkin_keyboard(meal_type):
    """Кнопки для чек-ина приёма пищи"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Поела!", callback_data=f"meal_done_{meal_type}"),
            InlineKeyboardButton("⏳ Скоро поем", callback_data=f"meal_soon_{meal_type}"),
        ],
        [InlineKeyboardButton("🎬 Перейти к занятию", callback_data="goto_exercise")],
    ])

def exercise_keyboard(day):
    """Кнопки для занятия"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Открыть занятие", url=f"{SITE_URL}/day{day}")],
        [
            InlineKeyboardButton("✅ Сделала занятие!", callback_data="done"),
            InlineKeyboardButton("⏳ Сделаю позже", callback_data="remind_later"),
        ],
    ])

def payment_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Оформить доступ", url=f"{SITE_URL}/#pricing")],
        [InlineKeyboardButton("✅ У меня есть номер заказа", callback_data="check_payment")],
    ])

# ══════════════════════════════════════════
# ТЕКСТЫ
# ══════════════════════════════════════════
MSG_WELCOME = """Привет! Это Рита! 🌸

Я так рада что ты здесь — значит ты уже сделала первый шаг к себе.

Just20 — это моя программа для занятых женщин. 20 минут в день, реальная еда, реальный результат — без наказаний и без стресса.

Чтобы начать — оформи доступ на сайте и возвращайся с номером заказа! 👇"""

MSG_NOT_PAID = """Привет! Это Рита 🌸

Чтобы получить доступ к программе — оформи его на сайте Just20 и пришли мне номер заказа из письма.

Я сразу всё открою! 💕"""

MSG_ACCESS_GRANTED = """🎉 Рита здесь! Ты теперь в программе Just20! 🌸

Вот что тебя ждёт каждый день:
🌅 В 9:00 — задание и меню на день
☀️ В 13:00 — напоминание об обеде
🌙 В 19:00 — напоминание об ужине

Каждое утро я буду рядом — как подруга которая верит в тебя!

Готова начать? 👇"""

# ══════════════════════════════════════════
# ДАННЫЕ ПО ДНЯМ
# ══════════════════════════════════════════
DAYS = {
    1: {
        "title": "День 1 — Первый шаг! 🌟",
        "exercise": "Пробуждение тела — 15 минут",
        "breakfast": "Овсянка с черникой и мёдом — 365 ккал",
        "lunch": "Куриный суп с овощами — 320 ккал",
        "dinner": "Запечённый лосось с брокколи — 310 ккал",
        "snack": "Яблоко + грецкие орехи — 185 ккал",
        "total": "~1380 ккал",
    },
    2: {
        "title": "День 2 — Продолжаем! 💪",
        "exercise": "Динамика и тонус — 17 минут",
        "breakfast": "Яичница с помидорами и шпинатом — 380 ккал",
        "lunch": "Гречка с куриной грудкой — 430 ккал",
        "dinner": "Греческий салат с тунцом — 310 ккал",
        "snack": "Апельсин + миндаль — 185 ккал",
        "total": "~1305 ккал",
    },
    3: {
        "title": "День 3 — Три дня — уже привычка! 🌿",
        "exercise": "Гибкость и осанка — 15 минут",
        "breakfast": "Сырники со сметаной — 385 ккал",
        "lunch": "Борщ с фасолью — 325 ккал",
        "dinner": "Запечённое куриное филе с овощами — 305 ккал",
        "snack": "Груша с творогом — 205 ккал",
        "total": "~1220 ккал",
    },
    4: {
        "title": "День 4 — Движение и сила ⚡",
        "exercise": "Ноги и ягодицы — 20 минут",
        "breakfast": "Творожная запеканка с бананом — 385 ккал",
        "lunch": "Рис с куриной грудкой — 415 ккал",
        "dinner": "Салат с тунцом и авокадо — 330 ккал",
        "snack": "Яблоко с арахисовой пастой — 200 ккал",
        "total": "~1330 ккал",
    },
    5: {
        "title": "День 5 — Баланс 🌸",
        "exercise": "Баланс и координация — 15 минут",
        "breakfast": "Гречневые блины с творогом — 355 ккал",
        "lunch": "Чечевичный суп — 365 ккал",
        "dinner": "Треска на пару с брокколи — 285 ккал",
        "snack": "Апельсин с кефиром — 165 ккал",
        "total": "~1170 ккал",
    },
    6: {
        "title": "День 6 — Ты в ритме! 🔥",
        "exercise": "Руки и плечи — 18 минут",
        "breakfast": "Овсянка с яблоком и орехами — 390 ккал",
        "lunch": "Курица с картофелем запечённая — 430 ккал",
        "dinner": "Творожный салат с огурцом — 195 ккал",
        "snack": "Виноград + сыр — 200 ккал",
        "total": "~1215 ккал",
    },
    7: {
        "title": "День 7 — Неделя 1 завершена! 🎉",
        "exercise": "Восстановление и растяжка — 15 минут",
        "breakfast": "Йогурт с гранолой и малиной — 370 ккал",
        "lunch": "Куриный плов — 465 ккал",
        "dinner": "Семга с зелёным салатом — 375 ккал",
        "snack": "Запечённое яблоко с мёдом — 215 ккал",
        "total": "~1425 ккал",
    },
}

for d in range(8, 22):
    DAYS[d] = {
        "title": f"День {d} 🌸",
        "exercise": f"Занятие {d} — открой в личном кабинете",
        "breakfast": "Смотри в плане питания",
        "lunch": "Смотри в плане питания",
        "dinner": "Смотри в плане питания",
        "snack": "Смотри в плане питания",
        "total": "~1400–1600 ккал",
    }

# ══════════════════════════════════════════
# УТРЕННЕЕ СООБЩЕНИЕ
# ══════════════════════════════════════════
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

def lunch_checkin(day):
    d = DAYS.get(day, DAYS[1])
    return f"""☀️ Привет! Рита проверяет 🌸

Уже обеденное время — как ты?

🍽️ *Обед сегодня:*
{d['lunch']}

Ты уже поела? 👇"""

def dinner_checkin(day):
    d = DAYS.get(day, DAYS[1])
    return f"""🌙 Добрый вечер! Это Рита 🌸

Заканчиваем день вместе!

🌙 *Ужин сегодня:*
{d['dinner']}

И не забудь про занятие если ещё не делала! 

Как прошёл твой день? 👇"""

# ══════════════════════════════════════════
# HANDLERS
# ══════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if user and user.get("active"):
        await update.message.reply_text(
            "Рита здесь! 🌸 Чем могу помочь?",
            reply_markup=main_keyboard()
        )
    else:
        await update.message.reply_text(MSG_WELCOME, reply_markup=payment_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id) or {}
    text = update.message.text.strip().lower()

    if user.get("waiting_payment_id"):
        await update.message.reply_text("🔍 Проверяю твою оплату...")
        result = await check_yukassa_payment(update.message.text.strip())
        if result["found"] and result["paid"]:
            activate_user(user_id)
            user["waiting_payment_id"] = False
            save_user(user_id, user)
            await update.message.reply_text(MSG_ACCESS_GRANTED, reply_markup=main_keyboard())
            try:
                await context.bot.send_message(ADMIN_ID,
                    f"✅ Новый покупатель!\nID: {user_id}\nИмя: {update.effective_user.full_name}")
            except:
                pass
        else:
            await update.message.reply_text(
                "Я не нашла этот номер заказа 🔍\n\nПроверь номер — он приходит на email после оплаты. Или напиши мне и разберёмся! 💕",
                reply_markup=payment_keyboard()
            )
        return

    if user.get("active"):
        if any(w in text for w in ["готово", "сделала", "готова", "done"]):
            await process_done(update, context)
        else:
            await update.message.reply_text(
                "Я здесь! 🌸\n\nИспользуй кнопки ниже или напиши что нужно 💕",
                reply_markup=main_keyboard()
            )
    else:
        await update.message.reply_text(MSG_NOT_PAID, reply_markup=payment_keyboard())

async def process_done(update, context):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user or not user.get("active"):
        return
    current_day = user.get("current_day", 1)
    import random
    responses = [
        "Умница! Я так тобой горжусь! 🎉🌸",
        "Вот это да! Ты сделала это! 💪🌸",
        "Браво! Каждый день ты становишься лучше! ✨🌸",
        "Это восхитительно! Так держать! 🔥🌸",
        "Ты — сила! Завтра продолжаем! 💕🌸",
    ]
    user["current_day"] = current_day + 1
    user["last_morning"] = datetime.now(MOSCOW_TZ).date().isoformat()
    save_user(user_id, user)
    msg = update.message if update.message else update.callback_query.message
    await msg.reply_text(
        f"{random.choice(responses)}\n\n"
        f"День {current_day} ✅ выполнен!\n\n"
        f"Завтра в 9:00 я пришлю тебе задание Дня {current_day + 1} 🌸",
        reply_markup=main_keyboard()
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id) or {}
    data = query.data

    if data == "check_payment":
        user["waiting_payment_id"] = True
        save_user(user_id, user)
        await query.message.reply_text(
            "Пришли мне номер заказа из письма которое пришло после оплаты 💕\n\n"
            "Он выглядит примерно так: 2c9a90be-000f-5000-a000-..."
        )

    elif data == "goto_exercise":
        if not user.get("active"):
            await query.message.reply_text(MSG_NOT_PAID, reply_markup=payment_keyboard())
            return
        day = user.get("current_day", 1)
        d = DAYS.get(day, DAYS[1])
        await query.message.reply_text(
            f"🎬 *{d['title']}*\n\n"
            f"Твоё занятие сегодня:\n*{d['exercise']}*\n\n"
            f"Открой личный кабинет на сайте Just20 и включай видео «День {day}»!\n\n"
            f"Я жду твоего «Готово»! 💕🌸",
            parse_mode="Markdown",
            reply_markup=exercise_keyboard(day)
        )

    elif data == "today":
        if not user.get("active"):
            await query.message.reply_text(MSG_NOT_PAID, reply_markup=payment_keyboard())
            return
        day = user.get("current_day", 1)
        await query.message.reply_text(
            morning_message(day),
            parse_mode="Markdown",
            reply_markup=exercise_keyboard(day)
        )

    elif data == "show_menu":
        if not user.get("active"):
            await query.message.reply_text(MSG_NOT_PAID, reply_markup=payment_keyboard())
            return
        day = user.get("current_day", 1)
        d = DAYS.get(day, DAYS[1])
        await query.message.reply_text(
            f"🥗 *Меню — День {day}*\n\n"
            f"☀️ Завтрак: {d['breakfast']}\n"
            f"🍎 Перекус: {d['snack']}\n"
            f"🍽️ Обед: {d['lunch']}\n"
            f"🌙 Ужин: {d['dinner']}\n\n"
            f"📊 Итого: {d['total']}\n"
            f"💧 Вода: 1.5–2 литра 🌸",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    elif data == "show_progress":
        if not user.get("active"):
            await query.message.reply_text(MSG_NOT_PAID, reply_markup=payment_keyboard())
            return
        day = user.get("current_day", 1)
        done = day - 1
        left = max(0, 21 - done)
        pct = min(100, int((done / 21) * 100))
        filled = int(pct / 10)
        bar = "🟣" * filled + "⬜" * (10 - filled)
        await query.message.reply_text(
            f"📊 *Твой прогресс Just20* 🌸\n\n"
            f"{bar} {pct}%\n\n"
            f"✅ Дней выполнено: {done}\n"
            f"⏳ Дней осталось: {left}\n\n"
            f"{'🎉 Ты прошла программу! Я так горжусь тобой!' if done >= 21 else 'Продолжай! Ты делаешь это! 💕'}\n\nРита 🌸",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )

    elif data == "done":
        update.message = query.message
        update.effective_user = query.from_user
        await process_done(update, context)

    elif data == "remind_later":
        await query.message.reply_text(
            "Хорошо! Я напомню тебе вечером 🌸\n\nНе забудь — занятие всего 20 минут. Ты можешь! 💕",
            reply_markup=main_keyboard()
        )

    elif data.startswith("meal_done_"):
        meal = data.replace("meal_done_", "")
        meal_names = {"breakfast": "завтрак", "lunch": "обед", "dinner": "ужин"}
        meal_ru = meal_names.get(meal, meal)
        await query.message.reply_text(
            f"Отлично! Ты поела {meal_ru} — это важно! 🌸\n\n"
            f"Регулярное питание держит метаболизм в тонусе 💕",
            reply_markup=main_keyboard()
        )

    elif data.startswith("meal_soon_"):
        meal = data.replace("meal_soon_", "")
        meal_names = {"breakfast": "завтракать", "lunch": "обедать", "dinner": "ужинать"}
        meal_ru = meal_names.get(meal, meal)
        await query.message.reply_text(
            f"Хорошо! Не забудь {meal_ru} — еда это топливо для твоего тела 🌸💕",
            reply_markup=main_keyboard()
        )

# ══════════════════════════════════════════
# YUKASSA
# ══════════════════════════════════════════
async def check_yukassa_payment(payment_id: str) -> dict:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.yookassa.ru/v3/payments/{payment_id}",
                auth=(YUKASSA_SHOP_ID, YUKASSA_SECRET_KEY),
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return {"found": True, "paid": data.get("status") == "succeeded"}
    except Exception as e:
        logging.error(f"YuKassa error: {e}")
    return {"found": False, "paid": False}

# ══════════════════════════════════════════
# РАССЫЛКИ — московское время
# ══════════════════════════════════════════
async def morning_broadcast(context: ContextTypes.DEFAULT_TYPE):
    """9:00 по Москве — задание дня"""
    db = load_db()
    today = datetime.now(MOSCOW_TZ).date().isoformat()
    for user_id, user in db.items():
        if not user.get("active"):
            continue
        day = user.get("current_day", 1)
        if day > 21:
            continue
        if user.get("last_morning") == today:
            continue
        try:
            await context.bot.send_message(
                int(user_id),
                morning_message(day),
                parse_mode="Markdown",
                reply_markup=exercise_keyboard(day)
            )
            user["last_morning"] = today
            save_user(user_id, user)
        except Exception as e:
            logging.error(f"Morning broadcast error {user_id}: {e}")

async def lunch_broadcast(context: ContextTypes.DEFAULT_TYPE):
    """13:00 по Москве — чек-ин обеда"""
    db = load_db()
    today = datetime.now(MOSCOW_TZ).date().isoformat()
    for user_id, user in db.items():
        if not user.get("active"):
            continue
        day = user.get("current_day", 1)
        if user.get("last_lunch") == today:
            continue
        try:
            await context.bot.send_message(
                int(user_id),
                lunch_checkin(day),
                parse_mode="Markdown",
                reply_markup=checkin_keyboard("lunch")
            )
            user["last_lunch"] = today
            save_user(user_id, user)
        except Exception as e:
            logging.error(f"Lunch broadcast error {user_id}: {e}")

async def dinner_broadcast(context: ContextTypes.DEFAULT_TYPE):
    """19:00 по Москве — чек-ин ужина"""
    db = load_db()
    today = datetime.now(MOSCOW_TZ).date().isoformat()
    for user_id, user in db.items():
        if not user.get("active"):
            continue
        day = user.get("current_day", 1)
        if user.get("last_dinner") == today:
            continue
        try:
            await context.bot.send_message(
                int(user_id),
                dinner_checkin(day),
                parse_mode="Markdown",
                reply_markup=checkin_keyboard("dinner")
            )
            user["last_dinner"] = today
            save_user(user_id, user)
        except Exception as e:
            logging.error(f"Dinner broadcast error {user_id}: {e}")

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
    db = load_db()
    total = len(db)
    active = sum(1 for u in db.values() if u.get("active"))
    await update.message.reply_text(
        f"📊 Статистика Just20\n\n"
        f"Всего пользователей: {total}\n"
        f"Активных: {active}\n"
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Привет! Это Рита* 🌸\n\n"
        "Используй кнопки ниже — они всегда доступны!\n\n"
        "Или напиши *готово* когда сделаешь занятие 💕",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ══════════════════════════════════════════
# ЗАПУСК
# ══════════════════════════════════════════
def main():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("activate", cmd_activate))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Рассылки по московскому времени
    import datetime as dt
    app.job_queue.run_daily(
        morning_broadcast,
        time=dt.time(9, 0, 0, tzinfo=MOSCOW_TZ),
        name="morning"
    )
    app.job_queue.run_daily(
        lunch_broadcast,
        time=dt.time(13, 0, 0, tzinfo=MOSCOW_TZ),
        name="lunch"
    )
    app.job_queue.run_daily(
        dinner_broadcast,
        time=dt.time(19, 0, 0, tzinfo=MOSCOW_TZ),
        name="dinner"
    )

    print("Just20 Bot v2 запущен! 🌸")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
