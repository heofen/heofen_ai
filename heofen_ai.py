import logging
import json
import time
import telebot
from telebot import types
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from groq import Groq
from datetime import datetime, timedelta
import random

# Настройка детального логирования
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Токены API
API_KEY = "7413001217:AAGNi4YerK7M-5kjAvl_wjCfTd3FG4HEFAU"
GROQ_API_KEY = "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"

bot = telebot.TeleBot(API_KEY)
client = Groq(api_key=GROQ_API_KEY)

MuteDuration = 300
kd = 30
mute_flag = True

user_dialogues = {}
user_modes = {}
users_time = {}
forwarded_messages = {}
lastUsage = 0

answers = [
    "Умный не тот, кто умный, а тот, кто с калькулятором",
    "Красив не тот, кто красив, а тот, у кого фильтры в Инстаграме",
    "Быстрый не тот, кто бежит, а тот, кто в лифте",
    "Добрый не тот, кто добрый, а тот, у кого конфет много",
    "Спящий не тот, кто спит, а тот, кто может",
    "Счастлив не тот, кто счастлив, а тот, кто с пиццей",
    "Знающий не тот, кто знает, а тот, у кого Google открыт"
]

def helpMessage(message):
    bot.reply_to(message, "Этот бот вобрал в себя всю шизу разраба\n\nЧто-бы бот ответил вам используйте в начале сообщения команду /ai")

lastUsages = {
    "1488": 1488
}

@bot.message_handler(commands=['m_duration'])
def mute_duration(message):
    chat_id = message.chat.id
    admins = bot.get_chat_administrators(chat_id)

    admin_list = []
    for admin in admins:
        user = admin.user
        admin_list.append(user.id)

    if message.from_user.id in admin_list and len(message.text.split()) == 2:
        global MuteDuration
        MuteDuration = int(message.text.split()[-1])
        bot.reply_to(message, f"Продолжительность мута равна {MuteDuration} секундам")

@bot.message_handler(commands=['ai_kd'])
def mute_duration(message):
    chat_id = message.chat.id
    admins = bot.get_chat_administrators(chat_id)

    admin_list = []
    for admin in admins:
        user = admin.user
        admin_list.append(user.id)

    if message.from_user.id in admin_list and len(message.text.split()) == 2:
        global kd
        kd = int(message.text.split()[-1])
        bot.reply_to(message, f"Кд равен {kd} секундам")

@bot.message_handler(commands=['switch_mute'])
def mute_duration(message):
    chat_id = message.chat.id
    admins = bot.get_chat_administrators(chat_id)

    admin_list = []
    for admin in admins:
        user = admin.user
        admin_list.append(user.id)

    if message.from_user.id in admin_list and len(message.text.split()) == 1:
        global mute_flag
        mute_flag = -mute_flag
        bot.reply_to(message, f"Режим антиспама переключен на {mute_flag}")

def mute(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Текущая временная метка + 5 минут (300 секунд)
    until_date = int(time.time()) + 300

    try:
        # Ограничиваем пользователя
        bot.restrict_chat_member(
            chat_id,
            user_id,
            until_date=until_date,
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False
        )
        if MuteDuration == 0:
            return 
        if MuteDuration < 60:
            mute_msg =  f"Пользователь {message.from_user.first_name} заглушен на {MuteDuration} секунд."
        else:
            mute_msg = f"Пользователь {message.from_user.first_name} заглушен на {MuteDuration // 60} минут."
        bot.reply_to(message, mute_msg)
    except Exception as e:
        bot.reply_to(message, f"Ошибка при заглушении: {e}")

def get_prompt():
    with open("prompt.txt", 'r', encoding='utf-8') as file:
        lines = file.readlines()
    return ''.join(line.strip() + '\n' for line in lines).strip()

# Чёрный список
def check_blacklist(user_id):
    try:
        with open("blacklist.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
        logging.debug(f"Blacklist data: {data}")
        return int(user_id) not in data["blacklist"]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading blacklist: {e}")
        return True

def add_blacklist(user_id):
    try:
        with open("blacklist.json", 'r+', encoding='utf-8') as f:
            data = json.load(f)
            data["blacklist"].append(int(user_id))
            f.seek(0)
            f.write(json.dumps(data, ensure_ascii=False, indent=4))
            f.truncate()
        logging.info(f"User {user_id} added to blacklist")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error updating blacklist: {e}")
        with open("blacklist.json", 'w', encoding='utf-8') as f:
            data = {"blacklist": [int(user_id)]}
            f.write(json.dumps(data, ensure_ascii=False, indent=4))

def check_spam(user_id):
    if not check_blacklist(user_id):
        return False

    user_id = str(user_id)
    if user_id not in users_time:
        users_time[user_id] = []

    users_time[user_id].append(time.time())

    if len(users_time[user_id]) > 5:
        users_time[user_id] = users_time[user_id][-5:]
        if users_time[user_id][-1] - users_time[user_id][0] < 10:
            add_blacklist(user_id)
            return False

    return True
    
# Получение ответа от Groq
def get_completion(messages):
    try:
        completion = client.chat.completions.create(
            model="gemma2-9b-it",
            messages=messages,
            temperature=0.70,
            max_tokens=900,
            top_p=1,
            stream=True
        )

        response = ""
        for chunk in completion:
            response += chunk.choices[0].delta.content or ""
        logging.debug(f"Response from Groq: {response}")
        return response
    except Exception as e:
        logging.error(f"Error getting completion: {e}")
        return f"Произошла ошибка при обработке вашего запроса. {e}"



# Обработчик сообщений
def handle_user_message(message, is_business=False):
    try:
        user_id = message.from_user.id
        logging.debug(f"Received message from {user_id}: {message.text}")
        logging.debug(f"Is business: {is_business}")

        if message.text.startswith("/ai "):
            text = message.text[4:]
        else:
            text = message.text

        if not check_spam(user_id):
            if is_business:
                bot.send_message(message.chat.id, "Вы были заблокированы за спам. За разбаном пишите в https://t.me/aikomarucardsbot", business_connection_id = is_business)
            else:
                bot.send_message(message.chat.id, "Вы были заблокированы за спам. За разбаном пишите в https://t.me/aikomarucardsbot")
            return

        if user_id not in user_dialogues:
            user_dialogues[user_id] = []

        if user_id not in user_modes:
            user_modes[user_id] = "AI"  # Default mode is AI

        if user_modes[user_id] == "AI":
            user_dialogues[user_id].append({"role": "user", "content": text})

            system_message = {
                "role": "system",
                "content": get_prompt()
            }
            user_dialogues[user_id].insert(0, system_message)
            logging.debug(f"Dialogue before completion: {user_dialogues[user_id]}")
            response = get_completion(user_dialogues[user_id])
            user_dialogues[user_id].pop(0)

            user_dialogues[user_id].append({"role": "assistant", "content": response})
            logging.debug(f"Dialogue after completion: {user_dialogues[user_id]}")

            buttons = [
                {
                    "text": "Очистить диалог",
                    "callback_data": "clear_dialogue"
                }
            ]
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(buttons[0]["text"], callback_data=buttons[0]["callback_data"]))
            if is_business:
                bot.send_message(message.chat.id, response, reply_markup=markup, business_connection_id = is_business)
            else:
                bot.reply_to(message, response, reply_markup=markup)
        else:
            sent_message = bot.forward_message(1268026433, message.chat.id, message.message_id)
            forwarded_messages[sent_message.message_id] = user_id
    except Exception as e:
        logging.error(f"Error handling message: {e}")


# @bot.business_message_handler(func=lambda message: True, content_types=['text'])
# def handle_business_message(message):
#     logging.debug("Handle business message")
#     logging.debug(f"Message JSON: {message.json}")
#
#     handle_user_message(message, is_business=message.business_connection_id)
    
@bot.message_handler(content_types=['text'])
def handle_private_message(message):
    global lastUsage
    global lastUsages
    logging.debug("Handle private message")
    logging.debug(f"Received message: {message}")
    if message.chat.id in [-1002212481103, -1002244372251]:
        if message.text == "/help" or message.text == "/help@heofenAiBot":
            helpMessage(message)
        if message.text.startswith("/ai") or (message.reply_to_message and message.reply_to_message.from_user.id == 7413001217):
            user_id = str(message.from_user.id)
            if user_id not in lastUsages:
                lastUsages[user_id] = 0
            if lastUsages[user_id] + kd > time.time() and mute_flag:
                mute(message)
            elif time.time() - lastUsage < 1.5:
                markup = InlineKeyboardMarkup()
                button = InlineKeyboardButton("Почему?", url="https://telegra.ph/Pochemu-speshka-ehto-ne-ochen-horosho-09-13")
                markup.add(button)
                bot.reply_to(message, "Не так быстро", reply_markup=markup)
                lastUsages[user_id] = time.time()
            elif (message.text == '/ai'):
                bot.reply_to(message, random.choice(answers))
                lastUsages[user_id] = time.time()
            else:
                handle_user_message(message, is_business=False)
                lastUsage = time.time()
                lastUsages[user_id] = time.time()
    else:
        bot.reply_to(message,
                     "Бот работает только в чате канала t.me/komaru_updates. Что-бы использовтать бота перейдите по ссылке")
        if message.chat.type in  ["supergroup", "group"]:
            bot.leave_chat(message.chat.id)


# Обработчик callback-запросов
@bot.callback_query_handler(func=lambda call: call.data in ["clear_dialogue"])
def handle_callback(call):
    try:
        user_id = call.from_user.id
        logging.debug(f"Callback query from {user_id}: {call.data}")

        if call.data == "clear_dialogue":
            if user_id in user_dialogues:
                user_dialogues[user_id] = []
            bot.answer_callback_query(call.id, "Диалог очищен.")
    except Exception as e:
        logging.error(f"Error handling callback query: {e}")

logging.info("Starting bot polling...")
try:
    bot.polling()
except Exception as e:
    logging.error(f"Error starting bot polling: {e}")
