import logging
import json
import time
import random

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions, Message
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# Логирование
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Настройка API ключей
API_KEY = "7413001217:AAGNi4YerK7M-5kjAvl_wjCfTd3FG4HEFAU"
genai.configure(api_key="AIzaSyArBxqYLLZs_U6f1ybL8Ngas0DP1q_EnKQ")

generation_config = {
    "temperature": 2,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

def get_prompt():
    with open("prompt.txt", 'r', encoding='utf-8') as file:
        lines = file.readlines()
    return ''.join(line.strip() + '\n' for line in lines).strip()

# Настройки модели
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    safety_settings={
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
    },
    system_instruction=get_prompt()
)

# Инициализация бота и диспетчера
bot = Bot(token=API_KEY)
dp = Dispatcher()

MuteDuration = 300
kd = 30
mute_flag = False

# Переменные для хранения данных пользователей
user_dialogues = {}
user_modes = {}
users_time = {}
forwarded_messages = {}
lastUsage = 0
lastUsages = {}

answers = [
    "Умный не тот, кто умный, а тот, кто с калькулятором",
    "Красив не тот, кто красив, а тот, у кого фильтры в Инстаграме",
    "Быстрый не тот, кто бежит, а тот, кто в лифте",
    "Добрый не тот, кто добрый, а тот, у кого конфет много",
    "Спящий не тот, кто спит, а тот, кто может",
    "Счастлив не тот, кто счастлив, а тот, кто с пиццей",
    "Знающий не тот, кто знает, а тот, у кого Google открыт"
]



async def clearHistory(user_id):
    global user_dialogues
    user_id = str(user_id)
    del(user_dialogues[user_id])

@dp.message(Command('m_duration'))
async def mute_duration(message: types.Message, command: CommandObject):
    chat_id = message.chat.id
    admins = await bot.get_chat_administrators(chat_id)
    admin_list = [admin.user.id for admin in admins]

    if message.from_user.id in admin_list and len(command.args.split()) == 1:
        global MuteDuration
        MuteDuration = int(command.args)
        await message.reply(f"Продолжительность мута изменена на {MuteDuration} секунд.")

@dp.message(Command('ai_kd'))
async def ai_kd(message: types.Message, command: CommandObject):
    chat_id = message.chat.id
    admins = await bot.get_chat_administrators(chat_id)
    admin_list = [admin.user.id for admin in admins]

    if message.from_user.id in admin_list and len(command.args.split()) == 1:
        global kd
        kd = int(command.args)
        await message.reply(f"Кд изменен на {kd} секунд.")


@dp.message(Command('switch_mute'))
async def switch_mute(message: types.Message):
    chat_id = message.chat.id
    admins = await bot.get_chat_administrators(chat_id)
    admin_list = [admin.user.id for admin in admins]

    if message.from_user.id in admin_list:
        global mute_flag
        mute_flag = not mute_flag
        await message.reply(f"Режим антиспама переключен на {mute_flag}.")


@dp.message(Command('adm_help'))
async def adm_help(message: types.Message):
    chat_id = message.chat.id
    admins = await bot.get_chat_administrators(chat_id)
    admin_list = [admin.user.id for admin in admins]

    if message.from_user.id in admin_list:
        await message.reply(f"Период мута: {MuteDuration} секунд\nКд: {kd} секунд\nРежим антиспама: {mute_flag}\n\n/m_duration <период> - изменить период мута\n/ai_kd <кд> - изменить кд\n/switch_mute - переключить режим антиспама")

async def mute(message: types.Message, duration=MuteDuration, reason = ""):
    user_id = message.from_user.id
    chat_id = message.chat.id
    until_date = int(time.time()) + duration

    try:
        await bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=False), until_date=until_date)
        if duration == 0:
            return
        if reason != "":
            reason = f"\nПричина: {reason}"
        mute_msg = f"Пользователь {message.from_user.first_name} заглушен на {duration // 60} минут.{reason}"
        await message.reply(mute_msg)
    except Exception as e:
        await message.reply(f"Ошибка при заглушении: {e}")

async def ban(message: Message):
    user_id = message.from_user.id
    chat_id = -1002212017812
    await bot.ban_chat_member(chat_id, user_id)

async def check_blacklist(user_id):
    try:
        with open("blacklist.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
        return int(user_id) not in data["blacklist"]
    except (FileNotFoundError, json.JSONDecodeError):
        return True

async def handle_user_message(message: types.Message, is_business=False):
    try:
        user_id = message.from_user.id
        logging.debug(f"Received message from {user_id}: {message.text}")
        logging.debug(f"Is business: {is_business}")

        if message.text.startswith("/ai "):
            text = message.text[4:]
        else:
            text = message.text

        if user_id not in user_dialogues:
            user_dialogues[user_id] = model.start_chat(history=[])

        if user_id not in user_modes:
            user_modes[user_id] = "AI"

        if user_modes[user_id] == "AI":
            response = user_dialogues[user_id].send_message(text)
            logging.debug(f"Dialogue after completion: {user_dialogues[user_id]}")

            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(text="Очистить диалог", callback_data=f"clear_dialogue_{str(message.from_user.id)}"))
            builder.as_markup()

            if is_business:
                await bot.send_message(message.chat.id, response.text, reply_markup=builder.as_markup())
            else:
                from deep_prompt_inspect import logging_ai
                await logging_ai(user_id, response.text, "AI")
                await message.reply(response.text, reply_markup=builder.as_markup(), parse_mode="MarkDown")

        else:
            sent_message = await bot.forward_message(1268026433, message.chat.id, message.message_id)
            forwarded_messages[sent_message.message_id] = user_id
    except Exception as e:
        await message.reply(f"Произошла ошибка {e}")

@dp.message()
async def handle_private_message(message: types.Message):
    global lastUsage
    global lastUsages

    if message.chat.id in [-1002244372251, -1002212017812] or message.chat.type == "private":
        from deep_prompt_inspect import censorProcessor
        if message.text == "/help":
            await message.reply("Этот бот вобрал в себя всю шизу разраба\n\nЧто-бы бот ответил вам используйте в начале сообщения команду /ai")
        if message.text.startswith("/ai") or (message.reply_to_message and message.reply_to_message.from_user.id == 7413001217) or message.chat.type == "private":
            user_id = str(message.from_user.id)
            if user_id not in lastUsages:
                lastUsages[user_id] = 0

            if lastUsages[user_id] + kd > time.time() and mute_flag:
                await mute(message)
            elif time.time() - lastUsage < 1.5:
                markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Почему спешка это плохо", url="https://telegra.ph/Pochemu-speshka-ehto-ne-ochen-horosho-09-13")]])
                await message.reply("Не так быстро", reply_markup=markup)
                lastUsages[user_id] = time.time()
            elif message.text == "/ai" and message.chat.type != "private":
                if await check_blacklist(user_id):
                    await message.reply(random.choice(answers))
                    lastUsages[user_id] = time.time()
                else:
                    await message.reply("Вы были заблокированы в боте")
            else:
                if await check_blacklist(user_id):
                    from deep_prompt_inspect import logging_ai
                    await logging_ai(user_id, message.text)
                    await handle_user_message(message)
                    lastUsage = time.time()
                    lastUsages[user_id] = time.time()
                else:
                    await message.reply("Вы были заблокированы в боте")
        else:
            # await censorProcessor(message)
            pass

    else:
        markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Я живу тут", url="https://t.me/+qemKO_g9GiRlYmRi")]])
        await message.reply("Бот работает только в чате канала. Чтобы использовать бота, нажмите кнопку ниже", reply_markup=markup)


@dp.callback_query(F.data.startswith("clear_dialogue_"))
async def clear_dialogue(callback_query: types.CallbackQuery):
    from deep_prompt_inspect import clearHistoryLogging
    user_id = callback_query.data.split('_')[-1]
    user_who_pressed = callback_query.from_user.id
    if int(user_id) == user_who_pressed:
        global user_dialogues
        if user_who_pressed in user_dialogues:
            print("История очищена")
            await callback_query.answer("Диалог очищен")
            del (user_dialogues[user_who_pressed])
            await clearHistoryLogging(str(user_who_pressed), "Inline by user", "pressed button")
        else:
            await callback_query.answer("Балбес, мы даже не общались")
    else:
        await callback_query.answer("Не ну ты ваще бобик ёбик")



async def main():
    await dp.start_polling(bot)
    await bot.send_message(chat_id=-1002212017812, text="Бот был перезапущен")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())