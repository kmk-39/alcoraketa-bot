import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                           ReplyKeyboardMarkup, KeyboardButton,
                           ReplyKeyboardRemove)
from aiogram.filters import CommandStart

###############################################################################
# КОНФИГУРАЦИЯ
###############################################################################
BOT_TOKEN = "7691178570:AAHVzzPYPbC5bbnp9mpHrEbVxjmgtjCDYNc"

CHANNEL_ID = -1002193668243  # Канал, на который надо подписаться
CHANNEL_INVITE_LINK = "https://t.me/+RjNhwct5B1wxOTEy"

REVIEWS_CHANNEL_LINK = "https://t.me/+VuaLFy5u-twwODRi"  # Ссылка на канал отзывов
ORDER_BOT_LINK = "https://t.me/deel1very_bot"           # Ссылка на бота для заказа

# file_id картинки (должен принадлежать ЭТОМУ боту)
PHOTO_FILE_ID = "AgACAgIAAxkBAAMbZ51movDjAAGyhx8jtw2Up1MUdB2VAAJu7zEbEF3pSBJhmyAAAfnKfwEAAwIAA3gAAzYE"

# Время, через которое считаем пользователя «бездействующим» (в сек.)
INACTIVITY_LIMIT = 120  # 2 минуты
# Проверка бездействия каждые X секунд
CHECK_INACTIVITY_INTERVAL = 30

# Через сколько секунд после подписки присылать «сообщение о подарке»?
# 24 часа = 86400 сек
GIFT_DELAY = 86400

###############################################################################
# ЛОГИ
###############################################################################
logging.basicConfig(level=logging.INFO)

###############################################################################
# ИНИЦИАЛИЗАЦИЯ
###############################################################################
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Храним различные данные о пользователях
users_data = {}  # user_id -> dict со статусами

"""
users_data[user_id] = {
    "last_activity": float,           # время последней активности
    "inactivity_msg_sent": bool,      # отправляли ли 1 раз сообщение о бездействии
    "subscribed_at": float,           # время, когда пользователь подписался
    "gift_msg_sent": bool,            # отправляли ли уже сообщение о подарке
    "collect_state": None / "phone" / "email",  # стадия сбора подарка
}
"""

###############################################################################
# ФУНКЦИЯ ПРОВЕРКИ ПОДПИСКИ
###############################################################################
async def check_subscription(user_id: int) -> bool:
    """
    Возвращает True, если user_id подписан на канал CHANNEL_ID.
    """
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

###############################################################################
# ОБНОВЛЯЕМ ВРЕМЯ ПОСЛЕДНЕЙ АКТИВНОСТИ
###############################################################################
def update_user_activity(user_id: int):
    if user_id not in users_data:
        users_data[user_id] = {
            "last_activity": 0,
            "inactivity_msg_sent": False,
            "subscribed_at": 0,
            "gift_msg_sent": False,
            "collect_state": None
        }
    users_data[user_id]["last_activity"] = asyncio.get_event_loop().time()

###############################################################################
# ХЕНДЛЕР /start
###############################################################################
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    update_user_activity(user_id)

    user_firstname = message.from_user.first_name or "друг"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔗Подписаться", url=CHANNEL_INVITE_LINK)
        ],
        [
            InlineKeyboardButton(text="✅Я подписался", callback_data="i_subscribed")
        ],
        [
            InlineKeyboardButton(text="✍🏼Отзывы", url=REVIEWS_CHANNEL_LINK)
        ]
    ])

    caption_text = (
        f"Привет, {user_firstname}!\n"
        f"Добро пожаловать в АЛКОРАКЕТА🚀\n"
        f"Мы круглосуточно доставляем напитки по лучшим ценам.\n\n"
        f"✨ Подпишись на наш канал, чтобы быть в курсе:\n"
        f"🔥 Горячих акций и скидок.\n"
        f"🍾 Новинок ассортимента.\n"
        f"🎉 Специальных предложений.\n\n"
        f"⬇ ДЛЯ ЗАКАЗА ПОДПИШИСЬ НА КАНАЛ ⬇"
    )

    await message.answer_photo(
        photo=PHOTO_FILE_ID,
        caption=caption_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )

###############################################################################
# ХЕНДЛЕР ЛЮБОГО СООБЩЕНИЯ -> ОБНОВЛЯЕМ АКТИВНОСТЬ
###############################################################################
@dp.message()
async def any_message_handler(message: types.Message):
    user_id = message.from_user.id
    # Обновляем время активности
    update_user_activity(user_id)

    # Если пользователь находится в режиме сбора данных "collect_state"
    state = users_data[user_id]["collect_state"]

    if state == "phone":
        # Проверяем: может быть user прислал контакт?
        if message.contact and message.contact.phone_number:
            phone = message.contact.phone_number
            # Сохраняем
            await message.answer(f"Принял твой номер телефона: {phone}")
            # Переходим к сбору email
            users_data[user_id]["collect_state"] = "email"
            await ask_email(message)
        else:
            # Или ввёл вручную?
            text = message.text.strip()
            # Простой паттерн проверки телефона (очень упрощённый)
            # допустим +7, 8, 10-значный, etc.
            pattern = r'^[\d+()\-\s]{5,}$'
            if re.match(pattern, text):
                await message.answer(f"Принял твой номер телефона: {text}")
                # Переходим к сбору email
                users_data[user_id]["collect_state"] = "email"
                await ask_email(message)
            else:
                await message.answer("Что-то не похоже на телефон. Введи ещё раз или отправь контакт.")

    elif state == "email":
        text = message.text.strip()
        # Упрощённая проверка email
        email_pattern = r'^[^@]+@[^@]+\.[^@]+$'
        if re.match(email_pattern, text):
            await message.answer("Отлично! Email принят.")
            # Выдаём промокод
            await message.answer("Твой промокод: <b>подписка24</b>\n\nСкидка 10% на следующий заказ!", parse_mode="HTML")
            # Сбрасываем состояние
            users_data[user_id]["collect_state"] = None
        else:
            await message.answer("Не похоже на email. Попробуй ещё раз.")

    else:
        # Если пользователь просто пишет что-то, когда мы не собираем данные
        pass

###############################################################################
# ХЕНДЛЕР: "Я ПОДПИСАЛСЯ"
###############################################################################
@dp.callback_query(F.data == "i_subscribed")
async def on_subscribed_button(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    update_user_activity(user_id)

    if await check_subscription(user_id):
        # Если подписан
        # Запоминаем время подписки
        users_data[user_id]["subscribed_at"] = asyncio.get_event_loop().time()

        text_subscribed = (
            "👀 Вижу нового подписчика!\n\n"
            "Спеши оформить заказ 👇"
        )
        keyboard_order = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🥂Заказать", url=ORDER_BOT_LINK)
            ],
            [
                InlineKeyboardButton(text="✍🏼Отзывы", url=REVIEWS_CHANNEL_LINK)
            ]
        ])
        await callback_query.message.answer(
            text_subscribed,
            parse_mode="HTML",
            reply_markup=keyboard_order
        )
    else:
        # Если НЕ подписан
        text_not_subscribed = (
            "🙈 Не вижу твоей подписки на канал «Алкоракета»🚀\n\n"
            "Подпишись на него, чтобы заказать доставку на дом."
        )
        await callback_query.message.answer(
            text_not_subscribed,
            parse_mode="HTML"
        )

    await callback_query.answer()

###############################################################################
# ФУНКЦИИ ДЛЯ ОТПРАВКИ ЗАПРОСА: ТЕЛЕФОН, EMAIL
###############################################################################
async def ask_phone(message: types.Message):
    """
    Просим пользователя ввести телефон.
    Предлагаем кнопку "Отправить контакт" (работает в мобильном Telegram).
    """
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отправить контакт", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        "Укажи, пожалуйста, свой номер телефона (можно нажать на кнопку ниже).",
        reply_markup=kb
    )

async def ask_email(message: types.Message):
    """
    Просим пользователя ввести email.
    """
    await message.answer(
        "Теперь введи свой e-mail:",
        reply_markup=ReplyKeyboardRemove()
    )

###############################################################################
# ФУНКЦИЯ: ОТПРАВКА "ПОДАРОК" ЧЕРЕЗ 24 ЧАСА
###############################################################################
async def send_gift_message(user_id: int):
    """
    Отправляет пользователю сообщение "Привет, вчера ты подписался... Хочешь подарок?"
    """
    text = (
        "Привет! Вчера ты подписался на наш канал, и сегодня у нас есть для тебя 🎁\n"
        "Хочешь забрать подарок? Нажми на кнопку!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Хочу подарок🎁", callback_data="get_gift")]
    ])
    try:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML",
            reply_markup=kb
        )
    except:
        pass

###############################################################################
# ХЕНДЛЕР: "ХОЧУ ПОДАРОК" (кнопка после 24 часов)
###############################################################################
@dp.callback_query(F.data == "get_gift")
async def on_get_gift(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    update_user_activity(user_id)

    # Начинаем собирать данные (phone, email)
    users_data[user_id]["collect_state"] = "phone"
    await callback_query.answer()
    # Просим телефон
    await ask_phone(callback_query.message)

###############################################################################
# ФОНОВАЯ ЗАДАЧА ДЛЯ БЕЗДЕЙСТВИЯ И ПОДАРКА
###############################################################################
async def background_tasks():
    while True:
        now = asyncio.get_event_loop().time()
        for user_id, data in list(users_data.items()):
            last_activity = data["last_activity"]

            # 1) Проверяем бездействие (если inactivity_msg_sent=False и > INACTIVITY_LIMIT)
            if not data["inactivity_msg_sent"]:
                if now - last_activity > INACTIVITY_LIMIT:
                    # Отправляем сообщение 1 раз
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text="Эй, ты где? Ты так и не нажал никаких кнопок...",
                        )
                    except:
                        pass
                    data["inactivity_msg_sent"] = True

            # 2) Проверяем, подписался ли пользователь и прошло ли 24 часа
            if data["subscribed_at"] > 0 and not data["gift_msg_sent"]:
                # время с момента подписки
                time_since_sub = now - data["subscribed_at"]
                if time_since_sub >= GIFT_DELAY:
                    # отправляем сообщение про подарок
                    await send_gift_message(user_id)
                    data["gift_msg_sent"] = True

        await asyncio.sleep(CHECK_INACTIVITY_INTERVAL)

###############################################################################
# ЗАПУСК БОТА
###############################################################################
async def main():
    asyncio.create_task(background_tasks())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())