"""
Just20 Telegram Bot — Полная версия
Рита говорит от первого лица
Доступ только после проверки оплаты через YuKassa
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
import httpx

# ══════════════════════════════════════════
# НАСТРОЙКИ — заменить своими данными
# ══════════════════════════════════════════
BOT_TOKEN = "8858775912:AAGrP1XCQAqdUUr0d7ffSR8esLwa3LRwRao"
YUKASSA_SHOP_ID = "ВАШ_SHOP_ID"
YUKASSA_SECRET_KEY = "ВАШ_SECRET_KEY"
ADMIN_ID = 8668453654  # Твой Telegram ID (узнать у @userinfobot)

# Ссылка на сайт Just20
SITE_URL = "https://just20.ru"

# ══════════════════════════════════════════
# БАЗА ДАННЫХ (простой JSON файл)
# ══════════════════════════════════════════
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
    db = load_db()
    return db.get(str(user_id), None)

def save_user(user_id, data):
    db = load_db()
    db[str(user_id)] = data
    save_db(db)

def activate_user(user_id, tariff="full"):
    """Активировать пользователя после оплаты"""
    user = get_user(user_id) or {}
    user.update({
        "active": True,
        "tariff": tariff,
        "start_date": datetime.now().isoformat(),
        "current_day": 1,
        "last_message": None,
    })
    save_user(user_id, user)

# ══════════════════════════════════════════
# ТЕКСТЫ БОТА — Рита говорит от первого лица
# ══════════════════════════════════════════

MSG_WELCOME = """Привет! Это Рита! 🌸

Я так рада что ты здесь — значит ты уже сделала первый шаг к себе.

Just20 — это моя программа которую я создала специально для таких женщин как мы с тобой. Занятых. Уставших после длинного дня. Хотящих перемен — но без страданий и наказаний.

20 минут в день. Реальная еда. Реальный результат.

Чтобы начать — нужно оформить доступ к программе. Выбери свой тариф на сайте и возвращайся с номером заказа! 👇"""

MSG_NOT_PAID = """Привет! Это Рита 🌸

Я вижу что у тебя пока нет доступа к программе.

Чтобы начать наш путь вместе — оформи доступ на сайте Just20 и пришли мне номер своего заказа.

Я проверю оплату и сразу открою тебе всё! 💕"""

MSG_ALREADY_ACTIVE = """Привет! Это Рита 🌸

Ты уже в программе — это так здорово! 

Используй /день чтобы получить задание на сегодня
Используй /меню чтобы посмотреть что приготовить
Используй /прогресс чтобы увидеть как далеко ты зашла 💕"""

MSG_ACCESS_GRANTED = """🎉 Рита здесь! И я так рада тебя видеть!

Твоя оплата подтверждена — добро пожаловать в Just20! 🌸

Вот что тебя ждёт:
• 21 день видеозанятий — 15-20 минут каждый день
• Готовые меню с рецептами на каждый день
• Списки покупок по неделям
• Я буду рядом каждый день!

Каждое утро я буду присылать тебе задание дня — занятие и меню.

Готова начать? Жми кнопку! 👇"""

MSG_PAYMENT_NOT_FOUND = """Я посмотрела но не нашла этот номер заказа 🔍

Проверь пожалуйста:
• Номер заказа приходит на email после оплаты
• Он выглядит примерно так: 2c9a90be-000f-5000-a000-...

Если что-то не получается — напиши мне прямо здесь и я разберусь! 💕"""

MSG_ADMIN_ACTIVATE = """✅ Пользователь активирован вручную!"""

# Сообщения для каждого из 21 дня
DAYS = {
    1: {
        "title": "День 1 — Первый шаг! 🌟",
        "message": """Привет! Это Рита и сегодня твой первый день! 🌸

Я так горжусь тобой — ты начала. Это уже больше чем делает большинство людей.

🎬 ЗАНЯТИЕ ДНЯ:
Сегодня мы начинаем мягко — занятие на пробуждение тела. Всего 15 минут. Включи видео «День 1» в своём личном кабинете и повторяй за мной.

🥗 МЕНЮ СЕГОДНЯ:
• Завтрак: Овсянка с черникой и мёдом (365 ккал)
• Перекус: Яблоко + грецкие орехи (185 ккал)
• Обед: Куриный суп с овощами (320 ккал)
• Ужин: Запечённый лосось с брокколи (310 ккал)

💧 Не забудь выпить 1.5-2 литра воды сегодня!

Итого: ~1380 ккал — ты сытая и в дефиците 💕

Напиши мне /готово когда сделаешь занятие — хочу знать как ты! 🌸""",
    },
    2: {
        "title": "День 2 — Продолжаем! 💪",
        "message": """Доброе утро! Это Рита 🌸

Ты вернулась — и это самое важное! День 2 — уже привычка начинается здесь.

🎬 ЗАНЯТИЕ ДНЯ:
Сегодня добавляем немного динамики. Видео «День 2» в личном кабинете. 17 минут — ты справишься!

🥗 МЕНЮ СЕГОДНЯ:
• Завтрак: Яичница с помидорами и шпинатом (380 ккал)
• Перекус: Апельсин + миндаль (185 ккал)
• Обед: Гречка с куриной грудкой и овощами (430 ккал)
• Ужин: Греческий салат с тунцом (310 ккал)

Итого: ~1305 ккал 💕

Напиши /готово когда закончишь занятие! 🌸""",
    },
    3: {
        "title": "День 3 — Три дня — это уже привычка! 🌿",
        "message": """Привет! Рита на связи 🌸

Знаешь что? Три дня подряд — это уже паттерн. Твой мозг начинает привыкать. Так держать!

🎬 ЗАНЯТИЕ ДНЯ:
Видео «День 3» — сегодня работаем на гибкость и осанку. 15 минут.

🥗 МЕНЮ СЕГОДНЯ:
• Завтрак: Сырники со сметаной (385 ккал)
• Перекус: Груша с творогом (205 ккал)
• Обед: Борщ с фасолью (325 ккал)
• Ужин: Запечённое куриное филе с овощами (305 ккал)

Итого: ~1220 ккал 💕

Как ты себя чувствуешь после 3 дней? Напиши мне! 🌸""",
    },
    4: {
        "title": "День 4 — Движение и сила ⚡",
        "message": """Доброе утро! Это Рита 🌸

День 4 — ты уже в ритме! Сегодня чуть активнее — но всё так же 20 минут.

🎬 ЗАНЯТИЕ ДНЯ:
Видео «День 4» — акцент на ноги и ягодицы. Тебе понравится!

🥗 МЕНЮ СЕГОДНЯ:
• Завтрак: Творожная запеканка с бананом (385 ккал)
• Перекус: Яблоко с арахисовой пастой (200 ккал)
• Обед: Рис с куриной грудкой (415 ккал)
• Ужин: Салат с тунцом и авокадо (330 ккал)

Итого: ~1330 ккал 💕

Напиши /готово после занятия! 🌸""",
    },
    5: {
        "title": "День 5 — Баланс 🌸",
        "message": """Привет! Рита здесь 🌸

Пятый день! Ты уже в середине первой недели — это невероятно!

🎬 ЗАНЯТИЕ ДНЯ:
Видео «День 5» — баланс и координация. Мягко и приятно.

🥗 МЕНЮ СЕГОДНЯ:
• Завтрак: Гречневые блины с творогом (355 ккал)
• Перекус: Апельсин с кефиром (165 ккал)
• Обед: Чечевичный суп (365 ккал)
• Ужин: Треска на пару с брокколи (285 ккал)

Итого: ~1170 ккал 💕

Ты делаешь это! 🌸""",
    },
    6: {
        "title": "День 6 — Ты в ритме! 🔥",
        "message": """Доброе утро! Рита на связи 🌸

День 6 — ты почти неделю! Я так тобой горжусь.

🎬 ЗАНЯТИЕ ДНЯ:
Видео «День 6» — работаем на руки и плечи. 18 минут.

🥗 МЕНЮ СЕГОДНЯ:
• Завтрак: Овсянка с яблоком и орехами (390 ккал)
• Перекус: Виноград + сыр (200 ккал)
• Обед: Курица с картофелем запечённая (430 ккал)
• Ужин: Творожный салат с огурцом (195 ккал)

Итого: ~1215 ккал 💕

Как тело себя чувствует? Пиши мне! 🌸""",
    },
    7: {
        "title": "День 7 — Неделя 1 завершена! 🎉",
        "message": """ПОЗДРАВЛЯЮ! Это Рита и я так горжусь тобой! 🎉🌸

Ты прошла целую неделю Just20. Это реальный результат — и ты это сделала!

🎬 ЗАНЯТИЕ ДНЯ:
Видео «День 7» — лёгкое восстановительное занятие и растяжка. Заслужила!

🥗 МЕНЮ СЕГОДНЯ:
• Завтрак: Йогурт с гранолой и малиной (370 ккал)
• Перекус: Запечённое яблоко с мёдом (215 ккал)
• Обед: Куриный плов (465 ккал)
• Ужин: Семга с зелёным салатом (375 ккал)

Итого: ~1425 ккал — сегодня немного больше, ты заслужила! 💕

Напиши мне как ты себя чувствуешь после первой недели — очень хочу знать! 🌸""",
    },
}

# Для дней 8-21 используем универсальное сообщение с заглушкой
for day in range(8, 22):
    week = 2 if day <= 14 else 3
    phase = "Трансформация" if week == 2 else "Закрепление"
    DAYS[day] = {
        "title": f"День {day} — {phase}! 🌸",
        "message": f"""Доброе утро! Это Рита 🌸

День {day} — ты продолжаешь и это самое главное!

🎬 ЗАНЯТИЕ ДНЯ:
Открой видео «День {day}» в своём личном кабинете.

🥗 МЕНЮ СЕГОДНЯ:
Открой план питания — меню на день {day} уже готово для тебя!

💧 Не забудь про воду — 1.5-2 литра сегодня!

Напиши /готово когда закончишь занятие — я буду ждать! 💕🌸"""
    }

# ══════════════════════════════════════════
# ПРОВЕРКА ОПЛАТЫ ЧЕРЕЗ YUKASSA
# ══════════════════════════════════════════
async def check_yukassa_payment(payment_id: str) -> dict:
    """Проверить статус платежа в YuKassa"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.yookassa.ru/v3/payments/{payment_id}",
                auth=(YUKASSA_SHOP_ID, YUKASSA_SECRET_KEY),
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "found": True,
                    "paid": data.get("status") == "succeeded",
                    "amount": data.get("amount", {}).get("value", "0"),
                    "metadata": data.get("metadata", {}),
                }
    except Exception as e:
        logging.error(f"YuKassa error: {e}")
    return {"found": False, "paid": False}

# ══════════════════════════════════════════
# HANDLERS
# ══════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if user and user.get("active"):
        keyboard = [[InlineKeyboardButton("📅 Моё задание на сегодня", callback_data="today")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(MSG_ALREADY_ACTIVE, reply_markup=reply_markup)
    else:
        keyboard = [
            [InlineKeyboardButton("💳 Оформить доступ", url=f"{SITE_URL}/#pricing")],
            [InlineKeyboardButton("✅ У меня есть номер заказа", callback_data="check_payment")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(MSG_WELCOME, reply_markup=reply_markup)

async def check_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Хорошо! Пришли мне номер своего заказа из письма которое пришло после оплаты.\n\n"
        "Он выглядит примерно так: 2c9a90be-000f-5000-a000-1b9b9b9b9b9b 💕"
    )
    # Сохраняем состояние ожидания номера заказа
    user = get_user(query.from_user.id) or {}
    user["waiting_payment_id"] = True
    save_user(query.from_user.id, user)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id) or {}
    text = update.message.text.strip()

    # Если ждём номер заказа
    if user.get("waiting_payment_id"):
        await update.message.reply_text("🔍 Проверяю твою оплату, секунду...")

        result = await check_yukassa_payment(text)

        if result["found"] and result["paid"]:
            activate_user(user_id)
            user["waiting_payment_id"] = False
            save_user(user_id, user)

            keyboard = [[InlineKeyboardButton("🚀 Начать День 1!", callback_data="day_1")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(MSG_ACCESS_GRANTED, reply_markup=reply_markup)

            # Уведомить администратора
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"✅ Новый покупатель!\n"
                    f"ID: {user_id}\n"
                    f"Имя: {update.effective_user.full_name}\n"
                    f"Username: @{update.effective_user.username}\n"
                    f"Заказ: {text}"
                )
            except:
                pass
        else:
            await update.message.reply_text(MSG_PAYMENT_NOT_FOUND)
        return

    # Если пользователь активен — обрабатываем команды текстом
    if user.get("active"):
        if "готово" in text.lower() or "сделала" in text.lower():
            await cmd_done(update, context)
        else:
            await update.message.reply_text(
                "Я здесь! 🌸\n\n"
                "Используй команды:\n"
                "/день — задание на сегодня\n"
                "/меню — меню дня\n"
                "/прогресс — твой прогресс\n"
                "/помощь — все команды"
            )
    else:
        await update.message.reply_text(MSG_NOT_PAID)

async def cmd_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Задание на текущий день"""
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user or not user.get("active"):
        await update.message.reply_text(MSG_NOT_PAID)
        return

    current_day = user.get("current_day", 1)

    if current_day > 21:
        await update.message.reply_text(
            "Ты прошла все 21 день! 🎉\n\n"
            "Это настоящий подвиг — я так тобой горжусь!\n\n"
            "Рита 🌸"
        )
        return

    day_data = DAYS.get(current_day, DAYS[1])
    await update.message.reply_text(
        f"*{day_data['title']}*\n\n{day_data['message']}",
        parse_mode="Markdown"
    )

async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь выполнила задание дня"""
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user or not user.get("active"):
        await update.message.reply_text(MSG_NOT_PAID)
        return

    current_day = user.get("current_day", 1)

    responses = [
        "Умница! Я так тобой горжусь! 🎉🌸",
        "Вот это да! Ты сделала это! 💪🌸",
        "Браво! Каждый день ты становишься лучшей версией себя! ✨🌸",
        "Это восхитительно! Так держать! 🔥🌸",
        "Ты — сила! Завтра продолжаем! 💕🌸",
    ]

    import random
    response = random.choice(responses)

    # Переводим на следующий день
    user["current_day"] = current_day + 1
    user["last_done"] = datetime.now().isoformat()
    save_user(user_id, user)

    await update.message.reply_text(
        f"{response}\n\n"
        f"День {current_day} ✅ выполнен!\n\n"
        f"Завтра утром я пришлю тебе задание Дня {current_day + 1} 🌸"
    )

async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню текущего дня"""
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user or not user.get("active"):
        await update.message.reply_text(MSG_NOT_PAID)
        return

    current_day = user.get("current_day", 1)
    day_data = DAYS.get(current_day, DAYS[1])

    # Извлекаем блок меню из сообщения
    message = day_data["message"]
    if "🥗 МЕНЮ" in message:
        menu_start = message.find("🥗 МЕНЮ")
        menu_end = message.find("💧", menu_start)
        if menu_end == -1:
            menu_end = message.find("Итого", menu_start) + 200
        menu_text = message[menu_start:menu_end].strip()
    else:
        menu_text = "Меню на день " + str(current_day) + " — смотри в документе Just20! 💕"

    await update.message.reply_text(
        f"*День {current_day} — меню*\n\n{menu_text}\n\n"
        f"Полные рецепты — в твоём личном кабинете Just20! 🌸",
        parse_mode="Markdown"
    )

async def cmd_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Прогресс пользователя"""
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user or not user.get("active"):
        await update.message.reply_text(MSG_NOT_PAID)
        return

    current_day = user.get("current_day", 1)
    days_done = current_day - 1
    days_left = max(0, 21 - days_done)
    percent = min(100, int((days_done / 21) * 100))

    # Прогресс-бар из эмодзи
    filled = int(percent / 10)
    bar = "🟣" * filled + "⬜" * (10 - filled)

    start_date = user.get("start_date", datetime.now().isoformat())
    try:
        start_dt = datetime.fromisoformat(start_date)
        days_since = (datetime.now() - start_dt).days + 1
    except:
        days_since = days_done

    await update.message.reply_text(
        f"*Твой прогресс Just20* 🌸\n\n"
        f"{bar} {percent}%\n\n"
        f"✅ Дней выполнено: {days_done}\n"
        f"⏳ Дней осталось: {days_left}\n"
        f"📅 В программе: {days_since} дней\n\n"
        f"{'🎉 Ты прошла программу! Я так тобой горжусь!' if days_done >= 21 else f'Продолжай! Ты делаешь это! 💕'}\n\n"
        f"Рита 🌸",
        parse_mode="Markdown"
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Привет! Это Рита* 🌸\n\n"
        "Вот что я умею:\n\n"
        "/день — задание на сегодня\n"
        "/готово — отметить что выполнила занятие\n"
        "/меню — меню питания на сегодня\n"
        "/прогресс — посмотреть прогресс\n"
        "/помощь — это сообщение\n\n"
        "Или просто напиши мне что угодно — я всегда здесь! 💕",
        parse_mode="Markdown"
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "check_payment":
        await check_payment_handler(update, context)
    elif data == "today":
        update.message = query.message
        update.effective_user = query.from_user
        await cmd_day(update, context)
    elif data.startswith("day_"):
        day_num = int(data.split("_")[1])
        user_id = query.from_user.id
        user = get_user(user_id) or {}
        user["current_day"] = day_num
        save_user(user_id, user)
        day_data = DAYS.get(day_num, DAYS[1])
        await query.message.reply_text(
            f"*{day_data['title']}*\n\n{day_data['message']}",
            parse_mode="Markdown"
        )

# ADMIN команды
async def cmd_admin_activate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вручную активировать пользователя /activate USER_ID"""
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Использование: /activate USER_ID")
        return

    target_id = int(context.args[0])
    activate_user(target_id)
    await update.message.reply_text(f"✅ Пользователь {target_id} активирован!")

    try:
        await context.bot.send_message(target_id, MSG_ACCESS_GRANTED)
    except:
        await update.message.reply_text("(не удалось отправить сообщение пользователю)")

async def cmd_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика /stats"""
    if update.effective_user.id != ADMIN_ID:
        return

    db = load_db()
    total = len(db)
    active = sum(1 for u in db.values() if u.get("active"))
    waiting = sum(1 for u in db.values() if u.get("waiting_payment_id"))

    await update.message.reply_text(
        f"📊 Статистика Just20\n\n"
        f"Всего пользователей: {total}\n"
        f"Активных: {active}\n"
        f"Ждут проверки: {waiting}\n"
    )

# ══════════════════════════════════════════
# ЕЖЕДНЕВНАЯ РАССЫЛКА
# ══════════════════════════════════════════
async def daily_broadcast(context: ContextTypes.DEFAULT_TYPE):
    """Каждый день в 9:00 отправлять задание активным пользователям"""
    db = load_db()

    for user_id, user in db.items():
        if not user.get("active"):
            continue

        current_day = user.get("current_day", 1)
        if current_day > 21:
            continue

        # Проверяем что сегодня ещё не отправляли
        last_msg = user.get("last_message")
        today = datetime.now().date().isoformat()
        if last_msg == today:
            continue

        day_data = DAYS.get(current_day, DAYS[1])

        try:
            await context.bot.send_message(
                int(user_id),
                f"*{day_data['title']}*\n\n{day_data['message']}",
                parse_mode="Markdown"
            )
            # Обновляем дату последнего сообщения
            user["last_message"] = today
            save_user(user_id, user)
        except Exception as e:
            logging.error(f"Ошибка отправки пользователю {user_id}: {e}")

# ══════════════════════════════════════════
# ЗАПУСК БОТА
# ══════════════════════════════════════════
def main():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )

    app = Application.builder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("день", cmd_day))
    app.add_handler(CommandHandler("den", cmd_day))
    app.add_handler(CommandHandler("готово", cmd_done))
    app.add_handler(CommandHandler("gotovo", cmd_done))
    app.add_handler(CommandHandler("меню", cmd_menu))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("прогресс", cmd_progress))
    app.add_handler(CommandHandler("progress", cmd_progress))
    app.add_handler(CommandHandler("помощь", cmd_help))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("activate", cmd_admin_activate))
    app.add_handler(CommandHandler("stats", cmd_admin_stats))

    # Кнопки
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Текстовые сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Ежедневная рассылка в 9:00
    app.job_queue.run_daily(
        daily_broadcast,
        time=datetime.strptime("09:00", "%H:%M").time(),
        name="daily_broadcast"
    )

    print("Just20 бот запущен! 🌸")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
