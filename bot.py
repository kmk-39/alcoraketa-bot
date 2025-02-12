import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.filters import CommandStart

###############################################################################
# КОНФИГУРАЦИЯ
###############################################################################
BOT_TOKEN = "7691178570:AAHVzzPYPbC5bbnp9mpHrEbVxjmgtjCDYNc"

CHANNEL_ID = -1002193668243  # ID канала, на который нужно подписаться
CHANNEL_INVITE_LINK = "https://t.me/+RjNhwct5B1wxOTEy"
REVIEWS_CHANNEL_LINK = "https://t.me/+VuaLFy5u-twwODRi"
ORDER_BOT_LINK = "https://t.me/@Alcoholgpt_bot"
PHOTO_FILE_ID = "AgACAgIAAxkBAAMbZ51movDjAAGyhx8jtw2Up1MUdB2VAAJu7zEbEF3pSBJhmyAAAfnKfwEAAwIAA3gAAzYE"

# ID закрытого канала для отправки собранных данных пользователей
PRIVATE_INFO_CHANNEL_ID = -1002458868061

# Время бездействия – 10 минут (600 секунд)
INACTIVITY_LIMIT = 600  
CHECK_INACTIVITY_INTERVAL = 30

# Задержка для отправки подарочного сообщения – 24 часа (86400 секунд)
GIFT_DELAY = 86400

###############################################################################
# ЛОГИРОВАНИЕ
###############################################################################
logging.basicConfig(level=logging.INFO)

###############################################################################
# ИНИЦИАЛИЗАЦИЯ
###############################################################################
from aiogram.client.bot import DefaultBotProperties
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# Структура хранения данных пользователя:
# users_data[user_id] = {
#    "last_activity": float,
#    "inactivity_msg_sent": bool,
#    "subscribed_at": float,      # время подписки (0 если не подписался)
#    "gift_msg_sent": bool,       # флаг отправки подарочного сообщения
#    "collect_state": None | "phone" | "email",  # этап сбора данных
#    "promo_received": bool,      # получил ли пользователь уже промокод
#    "phone": str,                # собранный номер телефона
#    "email": str                 # собранный email
# }
users_data = {}

def update_user_activity(user_id: int):
    if user_id not in users_data:
        users_data[user_id] = {
            "last_activity": 0,
            "inactivity_msg_sent": False,
            "subscribed_at": 0,
            "gift_msg_sent": False,
            "collect_state": None,
            "promo_received": False,
            "phone": "",
            "email": ""
        }
    users_data[user_id]["last_activity"] = asyncio.get_event_loop().time()

async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Ошибка проверки подписки для {user_id}: {e}")
        return False

###############################################################################
# ОБРАБОТЧИК /start
###############################################################################
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    update_user_activity(user_id)
    user_firstname = message.from_user.first_name or "друг"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Подписаться", url=CHANNEL_INVITE_LINK)],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="i_subscribed")],
        [InlineKeyboardButton(text="✍🏼 Отзывы", url=REVIEWS_CHANNEL_LINK)]
    ])
    
    caption_text = (
        f"Привет, {user_firstname}!\n"
        f"Добро пожаловать в АЛКОРАКЕТА🚀\n"
        f"Мы круглосуточно доставляем напитки по лучшим ценам.\n\n"
        f"✨ Подпишись на наш канал, чтобы быть в курсе:\n"
        f"🔥 Горячих акций и скидок.\n"
        f"🍾 Новинок ассортимента.\n"
        f"🎉 Специальных предложений.\n\n"
        f"⬇Для заказа подпишись на канал⬇"
    )
    
    await message.answer_photo(photo=PHOTO_FILE_ID, caption=caption_text, reply_markup=keyboard)

###############################################################################
# ОБРАБОТЧИК ЛЮБОГО СООБЩЕНИЯ (обновление активности и сбор данных)
###############################################################################
@dp.message()
async def any_message_handler(message: types.Message):
    user_id = message.from_user.id
    update_user_activity(user_id)
    state = users_data[user_id]["collect_state"]
    
    if state == "phone":
        if message.contact and message.contact.phone_number:
            phone = message.contact.phone_number
            users_data[user_id]["phone"] = phone
            await message.answer(f"Принял твой номер телефона: {phone}")
            users_data[user_id]["collect_state"] = "email"
            await ask_email(message)
        else:
            text = message.text.strip()
            pattern = r'^[\d+()\-\s]{5,}$'
            if re.match(pattern, text):
                users_data[user_id]["phone"] = text
                await message.answer(f"Принял твой номер телефона: {text}")
                users_data[user_id]["collect_state"] = "email"
                await ask_email(message)
            else:
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="cancel_collect")]
                ])
                await message.answer("Неверный формат номера телефона. Пожалуйста, проверь и введи снова или нажми 'Назад'.", reply_markup=kb)
    elif state == "email":
        text = message.text.strip()
        email_pattern = r'^[^@]+@[^@]+\.[^@]+$'
        if re.match(email_pattern, text):
            users_data[user_id]["email"] = text
            await message.answer("Отлично! Email принят.")
            if not users_data[user_id]["promo_received"]:
                promo_message = (
                    "Лови свой подарок! 🎁 Скидка 10% на следующий заказ! Назови оператору промокод <tg-spoiler>ПОДПИСКА24</tg-spoiler>"
                )
                await message.answer(promo_message)
                users_data[user_id]["promo_received"] = True
                # Отправка собранных данных в закрытый канал
                user_info = (
                    f"Пользователь: @{message.from_user.username or message.from_user.first_name}\n"
                    f"Номер: {users_data[user_id]['phone']}\n"
                    f"Email: {users_data[user_id]['email']}"
                )
                try:
                    await bot.send_message(chat_id=PRIVATE_INFO_CHANNEL_ID, text=user_info)
                except Exception as e:
                    logging.error(f"Ошибка отправки информации для {user_id}: {e}")
            users_data[user_id]["collect_state"] = None
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="cancel_collect")]
            ])
            await message.answer("Неверный формат email. Пожалуйста, введи корректный email или нажми 'Назад'.", reply_markup=kb)
    else:
        pass

###############################################################################
# ОБРАБОТЧИК КНОПКИ "Я ПОДПИСАЛСЯ"
###############################################################################
@dp.callback_query(F.data == "i_subscribed")
async def on_subscribed_button(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    update_user_activity(user_id)
    if await check_subscription(user_id):
        users_data[user_id]["subscribed_at"] = asyncio.get_event_loop().time()
        text_subscribed = "👀 Вижу нового подписчика!\n\nСпеши оформить заказ 👇"
        keyboard_order = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🥂 Заказать", url=ORDER_BOT_LINK)],
            [InlineKeyboardButton(text="✍🏼 Отзывы", url=REVIEWS_CHANNEL_LINK)]
        ])
        await callback_query.message.answer(text_subscribed, reply_markup=keyboard_order)
    else:
        text_not_subscribed = "🙈 Не вижу твоей подписки на канал «Алкоракета»🚀\n\nПодпишись на него, чтобы заказать доставку на дом."
        await callback_query.message.answer(text_not_subscribed)
    await callback_query.answer()

###############################################################################
# ОБРАБОТЧИК КНОПКИ "ДА, ХОЧУ ПОДАРОК!"
###############################################################################
@dp.callback_query(F.data == "get_gift")
async def on_get_gift(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    update_user_activity(user_id)
    users_data[user_id]["collect_state"] = "phone"
    await callback_query.answer()
    await ask_phone(callback_query.message)

###############################################################################
# ОБРАБОТЧИК КНОПКИ "НАЗАД"
###############################################################################
@dp.callback_query(F.data == "cancel_collect")
async def on_cancel_collect(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    update_user_activity(user_id)
    users_data[user_id]["collect_state"] = None
    await callback_query.message.answer("Ввод данных отменён.", reply_markup=ReplyKeyboardRemove())
    await callback_query.answer()

###############################################################################
# ФУНКЦИИ ДЛЯ ЗАПРОСА ТЕЛЕФОНА И EMAIL
###############################################################################
async def ask_phone(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отправить контакт", request_contact=True)],
            [KeyboardButton(text="Назад", callback_data="cancel_collect")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Чтобы забрать подарок, напиши свой номер телефона (или нажми 'Отправить контакт').", reply_markup=kb)

async def ask_email(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Назад", callback_data="cancel_collect")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Подарок уже близко, осталось совсем чуть-чуть🤏🏼 Напиши свой емэйл и подарок твой! 🎁", reply_markup=kb)

###############################################################################
# ФУНКЦИЯ: ОТПРАВКА ПОДАРОЧНОГО СООБЩЕНИЯ ЧЕРЕЗ 24 ЧАСА
###############################################################################
async def send_gift_message(user_id: int):
    text = (
        "Привет! Вчера ты подписался на наш канал, а сегодня у нас для тебя уже кое-что есть🎁\n"
        "Хочешь узнать подробнее? 😁"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, хочу подарок! 🎁", callback_data="get_gift")]
    ])
    try:
        await bot.send_message(chat_id=user_id, text=text, reply_markup=kb)
    except Exception as e:
        logging.error(f"Ошибка отправки подарочного сообщения для {user_id}: {e}")

###############################################################################
# ФОНОВАЯ ЗАДАЧА
###############################################################################
async def background_tasks():
    while True:
        now = asyncio.get_event_loop().time()
        for user_id, data in list(users_data.items()):
            # Если пользователь не подписался – отправляем сообщение о бездействии
            if not data["inactivity_msg_sent"] and data.get("subscribed_at", 0) == 0:
                if now - data["last_activity"] > INACTIVITY_LIMIT:
                    try:
                        inactivity_text = (
                            "Ваш заказ успешно оформлен и оплачен! Спасибо что выбрали наш сервис! Курьер уже выезжает!\n\n\n"
                            "Возможно мы поторопились? Кажется в системе пока нет Вашего заказа, исправим? Нажми подписаться и сделай свой первый заказ! 🥂"
                        )
                        await bot.send_message(chat_id=user_id, text=inactivity_text)
                    except Exception as e:
                        logging.error(f"Ошибка отправки сообщения о бездействии для {user_id}: {e}")
                    data["inactivity_msg_sent"] = True
            # Если пользователь подписался и прошло 24 часа, а подарок ещё не отправлен и промокод не получен
            if data.get("subscribed_at", 0) > 0 and not data["gift_msg_sent"] and not data.get("promo_received", False):
                time_since_sub = now - data["subscribed_at"]
                if time_since_sub >= GIFT_DELAY:
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