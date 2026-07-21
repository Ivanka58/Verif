import os
import logging
from telebot import TeleBot, types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- Настройки логирования ---
logging.basicConfig(level=logging.INFO)

# --- Переменные окружения (в Render добавишь их в Env) ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPPORT_GROUP_ID = os.getenv("SUPPORT_GROUP_ID")  # ID группы с Кентом (начинается с -100)
ADMIN_IDS = os.getenv("ADMIN_IDS")  # Строка с ID админов через запятую

# --- Словари состояний (для памяти) ---
user_states = {}  # {user_id: 'support'}
waiting_for_reply = {}  # В группе: {reply_message_id: user_id}

# --- Инициализация бота ---
bot = TeleBot(BOT_TOKEN)

# --- Главное меню (Старт) ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    text = (
        "🚀 *Добро пожаловать в Verif!*\n\n"
        "Я — твой умный помощник для проверки текстов и сайтов.\n"
        "⚡️ Быстро, точно и с ИИ.\n\n"
        "Выбери, что будем делать:"
    )
    markup = InlineKeyboardMarkup()
    btn1 = InlineKeyboardButton("🔍 Проверить текст", callback_data="text")
    btn2 = InlineKeyboardButton("🌐 Проверить сайт", callback_data="site")
    btn3 = InlineKeyboardButton("📞 Поддержка", callback_data="support")
    btn4 = InlineKeyboardButton("📖 Инструкция", callback_data="help")
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(commands=['support'])
def support_command(message):
    user_states[message.chat.id] = 'support'
    bot.send_message(message.chat.id, "📞 *Вы хотите отправить сообщение в техподдержку?*", 
                     reply_markup=InlineKeyboardMarkup().add(
                         InlineKeyboardButton("✉️ Отправить сообщение", callback_data="send_support")
                     ), parse_mode='Markdown')

# --- Обработка нажатий на кнопки ---
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    user_id = call.from_user.id
    
    if call.data == "support":
        bot.edit_message_text("📞 *Вы хотите отправить сообщение в техподдержку?*", 
                              chat_id=call.message.chat.id, 
                              message_id=call.message.message_id, 
                              reply_markup=InlineKeyboardMarkup().add(
                                  InlineKeyboardButton("✉️ Отправить сообщение", callback_data="send_support")
                              ), parse_mode='Markdown')
    
    elif call.data == "send_support":
        user_states[user_id] = 'support'
        bot.edit_message_text("✏️ Опишите вашу жалобу или вопрос максимально подробно.\nВы можете приложить фото и видео доказательства.", 
                              chat_id=call.message.chat.id, 
                              message_id=call.message.message_id)
    
    elif call.data == "exit_support":
        user_states[user_id] = None
        bot.edit_message_text("🚪 Вы вышли из поддержки. Если понадобится помощь — нажми /support.", 
                              chat_id=call.message.chat.id, 
                              message_id=call.message.message_id)
    
    elif call.data.startswith("reply_"):
        # Кнопка "Ответить" в группе с Кентом
        target_user_id = int(call.data.split("_")[1])
        waiting_for_reply[call.message.message_id] = target_user_id
        bot.send_message(call.message.chat.id, "✏️ Напишите ответ для пользователя:", reply_markup=types.ForceReply())

    elif call.data == "send_reply_yes":
        # Отправка ответа клиенту
        if call.message.reply_to_message:
            reply_text = call.message.reply_to_message.text
            # Ищем ID клиента в waiting_for_reply по ID сообщения, на которое ответили
            # (Это упрощенная логика, в реальной БД нужно хранить пары лучше)
            # Для примера мы используем сохраненное состояние из сообщения поддержки
            pass 
    
    elif call.data == "help":
        bot.edit_message_text("📖 *Инструкция:*\n\n1. Нажми 'Проверить текст' и вставь текст.\n2. Нажми 'Проверить сайт' и вставь ссылку.\n3. Все проверки бесплатны в рамках лимита.\n\nЕсли есть вопросы — пиши в Поддержку.", 
                              chat_id=call.message.chat.id, 
                              message_id=call.message.message_id, parse_mode='Markdown')

# --- Обработка сообщений от клиента (поддержка) ---
@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'support')
def handle_support_msg(message):
    user_id = message.chat.id
    
    # 1. Пересылаем в группу Кенту
    try:
        bot.forward_message(SUPPORT_GROUP_ID, user_id, message.message_id)
        # Добавляем подпись и кнопку
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✉️ Ответить", callback_data=f"reply_{user_id}"))
        mention = f"@{message.from_user.username}" if message.from_user.username else f"ID: {user_id}"
        bot.send_message(SUPPORT_GROUP_ID, f"📩 Пользователь {mention} отправил сообщение:", reply_markup=markup)
        
        # 2. Отвечаем клиенту
        bot.send_message(user_id, "✅ *Ваше сообщение отправлено в поддержку.*\nМы ответим вам в ближайшее время.", parse_mode='Markdown')
        
        # 3. Сбрасываем состояние (выходим из режима)
        user_states[user_id] = None
        bot.send_message(user_id, "Хотите написать еще?", 
                         reply_markup=InlineKeyboardMarkup().add(
                             InlineKeyboardButton("✏️ Написать еще", callback_data="send_support"),
                             InlineKeyboardButton("🚪 Выйти", callback_data="exit_support")
                         ))
    except Exception as e:
        bot.send_message(user_id, "❌ Ошибка при отправке. Попробуйте позже.")
        logging.error(f"Support error: {e}")

# --- Плашка для тестовых команд (заглушки) ---
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    if user_states.get(message.chat.id) == 'support':
        return  # уже обработано выше
    bot.reply_to(message, "Используй кнопки меню. Нажми /start, чтобы увидеть их.")

# --- Запуск бота ---
if __name__ == '__main__':
    print("🤖 Бот Verif запущен...")
    bot.infinity_polling()
