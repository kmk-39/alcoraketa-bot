import asyncio
import logging
import re
import time
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties

# Загрузка переменных окружения из .env файла
load_dotenv()

###############################################################################
# КОНФИГУРАЦИЯ (через переменные окружения)
###############################################################################
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env файле!")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
CHANNEL_INVITE_LINK = os.getenv("CHANNEL_INVITE_LINK")
REVIEWS_CHANNEL_LINK = os.getenv("REVIEWS_CHANNEL_LINK")
ORDER_BOT_LINK = os.getenv("ORDER_BOT_LINK")
PHOTO_FILE_ID = os.getenv("PHOTO_FILE_ID")
PRIVATE_INFO_CHANNEL_ID = int(os.getenv("PRIVATE_INFO_CHANNEL_ID"))

# Параметры таймингов
# Для неподписанных пользователей
INACTIVITY_LIMITS_NOT_SUBSCRIBED = [600, 1500, 86400]  # 10 минут, 25 минут, 24 часа
# Для зависания на сборе данных
INACTIVITY_LIMIT_DATA_COLLECTION = 300  # 5 минут
# Для подписанных пользователей (кликбейтные уведомления)
INACTIVITY_LIMITS_SUBSCRIBED = [
    86400,      # 1 день
    259200,     # 3 дня
    604800,     # 1 неделя
    1209600,    # 2 недели
    2592000,    # 1 месяц
    7776000,    # 3 месяца
    15552000    # 6 месяцев
]
CHECK_INACTIVITY_INTERVAL = 30  # Проверка каждые 30 секунд
GIFT_DELAY = 86400  # 24 часа

# Антиспам: минимальный интервал между сообщениями от одного пользователя (в секундах)
ANTI_SPAM_INTERVAL = 1  # 1 секунда

# Кликбейтные уведомления для неподписанных пользователей
INACTIVITY_MESSAGES_NOT_SUBSCRIBED = [
    "🔔 Осталось совсем чуть-чуть! Подпишись на наш канал и сделай свой первый заказ! 🚀",
    "⏳ Ты всё ещё с нами? Подпишись на канал, чтобы не упустить лучшие предложения! 🥂",
    "🎉 Не упусти шанс! Подпишись на канал и получи доступ к эксклюзивным скидкам! 🍾"
]

# Напоминание при зависании на сборе данных
INACTIVITY_MESSAGE_DATA_COLLECTION = "🎁 Подарок уже так близко! Заверши ввод данных, чтобы его забрать! ✨"

# Кликбейтные уведомления для подписанных пользователей
INACTIVITY_MESSAGES_SUBSCRIBED = [
    "🚀 Оплата прошла успешно! Ваш заказ уже в пути! 🎉\n\nОй, кажется, я перепутал! 😅 Не вижу твоего заказа... Но это легко исправить — оформи заказ прямо сейчас! 🥂",
    "📦 Ваш заказ доставлен! Проверьте, всё ли на месте! 🚚\n\nУпс, моя ошибка! 😳 Заказа пока нет, но я мечтаю, чтобы ты его оформил! Скорее закажи! 🍾",
    "🎉 Спасибо за заказ, оплата прошла! Скоро всё будет у вас! ✨\n\nИзвини, кажется, здесь ошибка... 😅 А я уже обрадовался! Не огорчай меня так, сделай заказ! 🚀",
    "🚚 Ваш заказ оформлен и оплачен! Спасибо за выбор нас! Курьер выезжает! 🎉\n\nВозможно, мы поторопились? 😳 Похоже, заказа нет. Подпишись и сделай заказ! 🥂",
    "🥳 Ваш заказ уже едет к вам! Ожидайте курьера! 🚚\n\nОй, кажется, я ошибся! 😜 Заказа пока нет, но я так хочу, чтобы ты его сделал! Оформи заказ и получи бонус! 🥂",
    "🍾 Оплата за ваш заказ прошла! Скоро всё будет у вас! 🎉\n\nУпс, перепутал! 😳 Заказа нет, но это мои мечты! Давай сделаем их реальностью — оформи заказ! 🍾",
    "🏆 Ваш заказ уже в пути! Проверьте статус доставки! 🚀\n\nОх, моя ошибка! 😅 Не вижу заказа, но я так хочу, чтобы ты его сделал! Оформи заказ и получи скидку! ✨"
]

###############################################################################
# ЛОГИРОВАНИЕ
###############################################################################
logging.basicConfig(level=logging.INFO)

###############################################################################
# ИНИЦИАЛИЗАЦИЯ
###############################################################################
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

# Глобальный словарь для хранения данных пользователей
users_data = {}

# Словарь для антиспама: хранит время последнего обработанного сообщения для каждого пользователя
last_message_time = {}

# Определение состояний для FSM
class CollectData(StatesGroup):
    phone = State()
    email = State()

def update_user_activity(user_id: int):
    """Обновляет время последней активности пользователя."""
    if user_id not in users_data:
        users_data[user_id] = {
            "last_activity": time.time(),
            "inactivity_messages_not_subscribed": [False] * len(INACTIVITY_LIMITS_NOT_SUBSCRIBED),  # Статус отправки для неподписанных
            "inactivity_message_data_collection_sent": False,  # Статус отправки при зависании на сборе данных
            "inactivity_messages_subscribed": [False] * len(INACTIVITY_LIMITS_SUBSCRIBED,  # Статус отправки для подписанных
            "subscribed_at": 0,
            "gift_msg_sent": False,
            "promo_received": False,
            "last_state": None  # Для отслеживания состояния FSM
        }
    else:
        users_data[user_id]["last_activity"] = time.time()

async def check_subscription(user_id: int) -> bool:
    """Проверяет, подписан ли пользователь на канал."""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Ошибка проверки подписки для {user_id}: {e}")
        try:
            await bot.send_message(user_id, "Ошибка при проверки подписки. Попробуй позже.")
        except Exception as send_err:
            logging.error(f"Ошибка отправки сообщения пользователю {user_id}: {send_err}")
        return False

def get_main_keyboard(user_firstname: str):
    """Возвращает приветственный текст и основную клавиатуру."""
    caption_text = (
        f"Привет, {user_firstname}!\n"
        "Добро пожаловать в АЛКОРАКЕТА🚀\n"
        "Мы круглосуточно доставляем напитки по лучшим ценам.\n\n"
        "✨ Подпишись на наш канал, чтобы быть в курсе:\n"
        "🔥 Горячих акций и скидок.\n"
        "🍾 Новинок ассортимента.\n"
        "🎉 Специальных предложений.\n\n"
        "⬇Для заказа подпишись на канал⬇"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Подписаться", url=CHANNEL_INVITE_LINK)],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="i_subscribed")],
        [InlineKeyboardButton(text="✍🏼 Отзывы", url=REVIEWS_CHANNEL_LINK)]
    ])
    return caption_text, keyboard

# Антиспам-фильтр
async def anti_spam_filter(user_id: int) -> bool:
    """Проверяет, прошло ли достаточно времени с последнего сообщения пользователя."""
    current_time = time.time()
    last_time = last_message_time.get(user_id, 0)
    if current_time - last_time < ANTI_SPAM_INTERVAL:
        return False  # Слишком быстро, игнорируем
    last_message_time[user_id] = current_time
    return True  # Можно обрабатывать

###############################################################################
# ОБРАБОТЧИКИ КОМАНД
###############################################################################
@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not await anti_spam_filter(user_id):
        return  # Игнорируем, если сообщение пришло слишком быстро
    update_user_activity(user_id)
    await state.clear()
    user_firstname = message.from_user.first_name or "друг"
    caption_text, keyboard = get_main_keyboard(user_firstname)
    await message.answer_photo(photo=PHOTO_FILE_ID, caption=caption_text, reply_markup=keyboard)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    user_id = message.from_user.id
    if not await anti_spam_filter(user_id):
        return
    help_text = (
        "Доступные команды:\n"
        "/start - Начать взаимодействие с ботом\n"
        "/help - Показать это сообщение\n"
        "/cancel - Отменить текущее действие"
    )
    await message.answer(help_text)

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not await anti_spam_filter(user_id):
        return
    update_user_activity(user_id)
    await state.clear()
    users_data[user_id]["last_state"] = None
    await message.answer("Действие отменено.", reply_markup=ReplyKeyboardRemove())

###############################################################################
# ОБРАБОТЧИК КНОПКИ "Я ПОДПИСАЛСЯ"
###############################################################################
@dp.callback_query(F.data == "i_subscribed")
async def on_subscribed_button(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    if not await anti_spam_filter(user_id):
        return
    update_user_activity(user_id)
    if await check_subscription(user_id):
        users_data[user_id]["subscribed_at"] = time.time()
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
async def on_get_gift(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    if not await anti_spam_filter(user_id):
        return
    update_user_activity(user_id)
    await state.set_state(CollectData.phone)
    users_data[user_id]["last_state"] = "CollectData.phone"
    await callback_query.answer()
    await ask_phone(callback_query.message)

###############################################################################
# ФУНКЦИИ ДЛЯ ЗАПРОСА ТЕЛЕФОНА И EMAIL
###############################################################################
async def ask_phone(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отправить контакт", request_contact=True)],
            [KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Чтобы забрать подарок, напиши свой номер телефона (или нажми 'Отправить контакт').", reply_markup=kb)

async def ask_email(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Подарок уже близко, осталось чуть-чуть🤏🏼 Напиши свой email и подарок твой! 🎁", reply_markup=kb)

###############################################################################
# ОБРАБОТЧИК СООБЩЕНИЙ В СОСТОЯНИИ СБОРА ДАННЫХ
###############################################################################
@dp.message(CollectData.phone)
async def process_phone(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not await anti_spam_filter(user_id):
        return
    update_user_activity(user_id)
    users_data[user_id]["last_state"] = "CollectData.phone"
    if message.text and message.text.strip() == "Назад":
        await state.clear()
        users_data[user_id]["last_state"] = None
        await message.answer("Ввод отменён.", reply_markup=ReplyKeyboardRemove())
        return

    if message.contact:
        phone = message.contact.phone_number
    else:
        text = message.text.strip()
        phone_pattern = r'^\+?\d{9,15}$'
        if re.match(phone_pattern, text):
            phone = text
        else:
            await message.answer("Неверный формат номера. Введи снова или нажми 'Назад'.")
            return
    await state.update_data(phone=phone)
    await message.answer(f"Принял телефон: {phone}", reply_markup=ReplyKeyboardRemove())
    await state.set_state(CollectData.email)
    users_data[user_id]["last_state"] = "CollectData.email"
    await ask_email(message)

@dp.message(CollectData.email)
async def process_email(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not await anti_spam_filter(user_id):
        return
    update_user_activity(user_id)
    users_data[user_id]["last_state"] = "CollectData.email"
    if message.text.strip() == "Назад":
        await state.set_state(CollectData.phone)
        users_data[user_id]["last_state"] = "CollectData.phone"
        await ask_phone(message)
        return

    text = message.text.strip()
    email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if re.match(email_pattern, text):
        await state.update_data(email=text)
        data = await state.get_data()
        phone = data.get("phone", "")
        email = data.get("email", "")
        await message.answer("Отлично! Email принят.", reply_markup=ReplyKeyboardRemove())
        if not users_data[user_id]["promo_received"]:
            promo_message = (
                "Лови свой подарок! 🎁 Скидка 10% на следующий заказ! "
                "Назови оператору промокод <tg-spoiler>ПОДПИСКА24</tg-spoiler>"
            )
            await message.answer(promo_message)
            users_data[user_id]["promo_received"] = True
            user_info = (
                f"Пользователь: @{message.from_user.username or message.from_user.first_name}\n"
                f"Номер: {phone}\n"
                f"Email: {email}"
            )
            try:
                await bot.send_message(chat_id=PRIVATE_INFO_CHANNEL_ID, text=user_info)
            except Exception as e:
                logging.error(f"Ошибка отправки информации для {user_id}: {e}")
        await state.clear()
        users_data[user_id]["last_state"] = None
    else:
        await message.answer("Неверный формат email. Введи снова или нажми 'Назад'.")

###############################################################################
# ФУНКЦИЯ: ОТПРАВКА ПОДАРОЧНОГО СООБЩЕНИЯ ЧЕРЕЗ 24 ЧАСА
###############################################################################
async def send_gift_message(user_id: int):
    text = (
        "Привет! Вчера ты подписался на наш канал, а сегодня у нас для тебя подарок🎁\n"
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
        now = time.time()
        tasks = []
        for user_id, data in list(users_data.items()):
            # Проверка бездействия для неподписанных пользователей
            if data.get("subscribed_at", 0) == 0:
                for i, limit in enumerate(INACTIVITY_LIMITS_NOT_SUBSCRIBED):
                    if not data["inactivity_messages_not_subscribed"][i] and (now - data["last_activity"] > limit):
                        tasks.append(bot.send_message(chat_id=user_id, text=INACTIVITY_MESSAGES_NOT_SUBSCRIBED[i]))
                        data["inactivity_messages_not_subscribed"][i] = True

            # Проверка бездействия на этапе сбора данных
            if data.get("last_state") in ["CollectData.phone", "CollectData.email"]:
                if not data["inactivity_message_data_collection_sent"] and (now - data["last_activity"] > INACTIVITY_LIMIT_DATA_COLLECTION):
                    tasks.append(bot.send_message(chat_id=user_id, text=INACTIVITY_MESSAGE_DATA_COLLECTION))
                    data["inactivity_message_data_collection_sent"] = True

            # Проверка подарочного сообщения для подписанных пользователей
            if data.get("subscribed_at", 0) > 0 and not data["gift_msg_sent"] and not data.get("promo_received", False):
                time_since_sub = now - data["subscribed_at"]
                if time_since_sub >= GIFT_DELAY:
                    tasks.append(send_gift_message(user_id))
                    data["gift_msg_sent"] = True

            # Проверка кликбейтных сообщений для всех подписанных пользователей
            if data.get("subscribed_at", 0) > 0:
                time_since_sub = now - data["subscribed_at"]
                for i, limit in enumerate(INACTIVITY_LIMITS_SUBSCRIBED):
                    if not data["inactivity_messages_subscribed"][i] and (time_since_sub > limit):
                        tasks.append(bot.send_message(chat_id=user_id, text=INACTIVITY_MESSAGES_SUBSCRIBED[i]))
                        data["inactivity_messages_subscribed"][i] = True

        if tasks:
            try:
                await asyncio.gather(*tasks)
            except Exception as e:
                logging.error(f"Ошибка в фоновых задачах: {e}")
        await asyncio.sleep(CHECK_INACTIVITY_INTERVAL)

###############################################################################
# ЗАПУСК БОТА
###############################################################################
async def main():
    asyncio.create_task(background_tasks())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
