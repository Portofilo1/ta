import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import datetime
import time
import requests
import json
import threading
import logging
import os
from database import init_db, get_user, update_balance, add_purchase, save_invoice, update_invoice_status, get_active_invoices

# ---------- НАСТРОЙКИ ----------
BOT_TOKEN = '8724690198:AAEn4dErZuQQhPzciHEw7Idw0MVhI4jsOsE'  # Токен от BotFather
CRYPTOBOT_TOKEN = '484573:AAsun5Rhpii35W2kUrabnhWuU6t7Fojp6Qt'  # Токен от CryptoBot
ADMIN_ID = 7395194688  # Ваш Telegram ID
CRYPTOBOT_API_URL = 'https://pay.crypt.bot/api'
# --------------------------------

bot = telebot.TeleBot(BOT_TOKEN)
logging.basicConfig(level=logging.INFO)

# Инициализация базы данных
init_db()

# Хранилище временных данных
user_states = {}

# ---------- ОПЕРАТОРЫ И ЦЕНЫ ----------
OPERATORS = {
    'megafon': {
        'name': 'Мегафон 4.0', 
        'price': 4.0, 
        'type': 'сим/eSIM',
        'photo': 'photos/megafon.jpg',  # ← путь в папке photos
        'caption': 'Мегафон 4.0 - подпись сим'
    },
    'mts': {
        'name': 'МТС 5.3', 
        'price': 5.3, 
        'type': 'сим/eSIM',
        'photo': 'photos/mts.jpg',       # ← путь в папке photos
        'caption': 'МТС 5.3 - подпись сим'
    },
    'beeline': {
        'name': 'Билайн', 
        'price': 3.0, 
        'type': 'сим/eSIM',
        'photo': 'photos/beeline.jpg',   # ← путь в папке photos
        'caption': 'Билайн - подпись сим'
    },
    't2': {
        'name': 'T2', 
        'price': 2.5, 
        'type': 'сим/eSIM',
        'photo': 'photos/t2.jpg',        # ← путь в папке photos
        'caption': 'T2 - подпись сим'
    },
    'sber': {
        'name': 'СБЕР', 
        'price': 2.5, 
        'type': 'сим/eSIM',
        'photo': 'photos/sber.jpg',      # ← путь в папке photos
        'caption': 'СБЕР - подпись сим'
    },
    'tmobile': {
        'name': 'Т-Мобайл', 
        'price': 2.2, 
        'type': 'сим',
        'photo': 'photos/tmobile.jpg',   # ← путь в папке photos
        'caption': 'Т-Мобайл - подпись сим'
    },
    'other': {
        'name': 'Другие операторы', 
        'price': 0, 
        'type': 'договорная',
        'photo': 'photos/other.jpg',     # ← путь в папке photos
        'caption': 'Другие операторы - цена договорная'
    }
}

# ---------- ФУНКЦИИ ДЛЯ РАБОТЫ С CRYPTO BOT ----------
def create_crypto_invoice(amount, user_id):
    """Создание счета в Crypto Bot"""
    headers = {'Crypto-Pay-API-Token': CRYPTOBOT_TOKEN}
    payload = {
        'amount': amount,
        'currency_type': 'crypto',
        'asset': 'USDT',
        'description': f'Пополнение баланса Gkey Market для пользователя {user_id}'
    }
    try:
        response = requests.post(f'{CRYPTOBOT_API_URL}/createInvoice', headers=headers, json=payload)
        data = response.json()
        if data['ok']:
            return data['result']
        else:
            logging.error(f"CryptoBot error: {data}")
            return None
    except Exception as e:
        logging.error(f"Error creating invoice: {e}")
        return None

def check_invoice_status(invoice_id):
    """Проверка статуса счета"""
    headers = {'Crypto-Pay-API-Token': CRYPTOBOT_TOKEN}
    payload = {'invoice_ids': invoice_id}
    try:
        response = requests.post(f'{CRYPTOBOT_API_URL}/getInvoices', headers=headers, json=payload)
        data = response.json()
        if data['ok'] and data['result']['items']:
            return data['result']['items'][0]['status']
        return None
    except Exception as e:
        logging.error(f"Error checking invoice: {e}")
        return None

# ---------- АВТОПРОВЕРКА СЧЕТОВ КАЖДЫЕ 5 СЕКУНД ----------
def check_payments_loop():
    """Автопроверка статусов счетов каждые 5 секунд"""
    while True:
        try:
            # Получаем все активные инвойсы из БД
            active_invoices = get_active_invoices()
            
            for inv in active_invoices:
                invoice_id = inv[0]
                user_id = inv[1]
                amount = inv[2]
                
                # Проверяем статус
                status = check_invoice_status(invoice_id)
                
                if status == 'paid':
                    # Начисляем баланс
                    update_balance(user_id, amount)
                    update_invoice_status(invoice_id, 'paid')
                    
                    # Уведомляем пользователя
                    try:
                        bot.send_message(
                            user_id,
                            f"Пополнение на {amount} USDT успешно!\n"
                            f"Средства зачислены на баланс."
                        )
                    except:
                        pass
                    
                elif status in ['expired', 'cancelled']:
                    update_invoice_status(invoice_id, status)
            
        except Exception as e:
            logging.error(f"Error in payment check loop: {e}")
        
        time.sleep(5)  # Проверка каждые 5 секунд

# ---------- ГЛАВНОЕ МЕНЮ ----------
def main_menu():
    """Инлайн клавиатура главного меню"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Подписать сим", callback_data="subscribe"),
        InlineKeyboardButton("Пополнить баланс", callback_data="deposit"),
        InlineKeyboardButton("Профиль", callback_data="profile"),
        InlineKeyboardButton("Помощь", callback_data="help")
    )
    return markup

def operators_keyboard():
    """Клавиатура с операторами"""
    markup = InlineKeyboardMarkup(row_width=1)
    for key, op in OPERATORS.items():
        button_text = f"{op['name']} - {op['price'] if op['price'] > 0 else 'договорная'} USDT"
        markup.add(InlineKeyboardButton(button_text, callback_data=f"op_{key}"))
    markup.add(InlineKeyboardButton("« Назад в меню", callback_data="back_to_menu"))
    return markup

# ---------- ОБРАБОТЧИКИ КОМАНД ----------
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Регистрируем пользователя в БД
    conn = sqlite3.connect('gkey_market.db')
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, balance, purchases_count, registered_at) 
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, 0, 0, now))
    conn.commit()
    conn.close()
    
    bot.send_message(
        message.chat.id,
        "Добро пожаловать в Gkey Market\n\n"
        "Здесь вы можете сделать подпись симки\n"
        "Используйте кнопки ниже для навигации:",
        reply_markup=main_menu()
    )

# ---------- ОБРАБОТЧИКИ INLINE КНОПОК ----------
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    
    if call.data == "profile":
        show_profile(call)
    
    elif call.data == "deposit":
        show_deposit_options(call)
    
    elif call.data.startswith("deposit_"):
        amount = call.data.split("_")[1]
        process_deposit(call, amount)
    
    elif call.data == "subscribe":
        show_operators(call)
    
    elif call.data.startswith("op_"):
        operator_key = call.data.split("_")[1]
        show_operator_confirmation(call, operator_key)
    
    elif call.data.startswith("confirm_"):
        operator_key = call.data.split("_")[1]
        process_purchase(call, operator_key)
    
    elif call.data == "back_to_menu":
        bot.edit_message_text(
            "Главное меню:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_menu()
        )
    
    elif call.data == "back_to_operators":
        show_operators(call)
    
    elif call.data == "help":
        bot.edit_message_text(
            "Помощь:\n\n"
            f"По всем вопросам обращайтесь к администратору",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_menu()
        )

def show_profile(call):
    """Показать профиль пользователя"""
    user_id = call.from_user.id
    user_data = get_user(user_id)
    
    if user_data:
        balance = user_data[2]  # balance
        purchases = user_data[3]  # purchases_count
        
        text = f"Профиль:\n\n"
        text += f"ID: {user_id}\n"
        text += f"Баланс: {balance} USDT\n"
        text += f"Всего покупок: {purchases}"
    else:
        text = "Профиль не найден"
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=main_menu()
    )

def show_deposit_options(call):
    """Показать варианты пополнения"""
    markup = InlineKeyboardMarkup(row_width=2)
    amounts = [10, 20, 50, 100, 200, 500]
    
    for amount in amounts:
        markup.add(InlineKeyboardButton(f"{amount} USDT", callback_data=f"deposit_{amount}"))
    
    markup.add(InlineKeyboardButton("« Назад", callback_data="back_to_menu"))
    
    bot.edit_message_text(
        "Выберите сумму пополнения в USDT:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

def process_deposit(call, amount):
    """Обработка пополнения через CryptoBot"""
    user_id = call.from_user.id
    
    # Создаем счет в Crypto Bot
    invoice = create_crypto_invoice(amount, user_id)
    
    if invoice:
        # Сохраняем инвойс в БД
        save_invoice(invoice['invoice_id'], user_id, amount)
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Оплатить", url=invoice['pay_url']))
        markup.add(InlineKeyboardButton("« Отмена", callback_data="deposit"))
        
        bot.edit_message_text(
            f"Счет на {amount} USDT создан\n\n"
            f"После оплаты средства будут зачислены автоматически",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
    else:
        bot.answer_callback_query(call.id, "Ошибка создания счета. Попробуйте позже.")

def show_operators(call):
    """Показать список операторов"""
    bot.edit_message_text(
        "Выберите оператора для подписи сим:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=operators_keyboard()
    )

def show_operator_confirmation(call, operator_key):
    """Показать фото и подтверждение для конкретного оператора"""
    operator = OPERATORS.get(operator_key)
    if not operator:
        bot.answer_callback_query(call.id, "Оператор не найден")
        return
    
    user_id = call.from_user.id
    user_data = get_user(user_id)
    balance = user_data[2] if user_data else 0
    
    # Клавиатура подтверждения
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Да", callback_data=f"confirm_{operator_key}"),
        InlineKeyboardButton("Назад", callback_data="back_to_operators")
    )
    
    # Текст подтверждения
    if operator['price'] > 0:
        price_text = f"Вы покупаете Подпись {operator['name']} за {operator['price']} USDT"
    else:
        price_text = f"Вы покупаете Подпись {operator['name']} (цена договорная)"
    
    caption = (f"Внимательно посмотрите\n\n"
               f"{price_text}\n"
               f"Ваш баланс: {balance} USDT\n\n"
               f"Вы подтверждаете?")
    
    # Отправляем фото (если есть) или просто текст
    try:
        if os.path.exists(operator['photo']):
            with open(operator['photo'], 'rb') as photo:
                bot.send_photo(
                    call.message.chat.id,
                    photo,
                    caption=caption,
                    reply_markup=markup
                )
            # Удаляем предыдущее сообщение с меню
            bot.delete_message(call.message.chat.id, call.message.message_id)
        else:
            # Если фото нет, редактируем текущее сообщение
            bot.edit_message_text(
                caption,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
    except Exception as e:
        logging.error(f"Error sending photo: {e}")
        # Если ошибка с фото, отправляем просто текст
        bot.edit_message_text(
            caption,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )

def process_purchase(call, operator_key):
    """Обработка покупки (подписи сим)"""
    user_id = call.from_user.id
    operator = OPERATORS.get(operator_key)
    
    if not operator:
        bot.answer_callback_query(call.id, "Оператор не найден")
        return
    
    # Получаем баланс пользователя
    user_data = get_user(user_id)
    balance = user_data[2] if user_data else 0
    
    # Для операторов с договорной ценой пропускаем проверку баланса
    if operator['price'] > 0 and balance < operator['price']:
        bot.answer_callback_query(
            call.id, 
            f"Недостаточно средств. Нужно {operator['price']} USDT"
        )
        return
    
    # Списываем баланс (если цена не договорная)
    if operator['price'] > 0:
        conn = sqlite3.connect('gkey_market.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', 
                      (operator['price'], user_id))
        conn.commit()
        conn.close()
    
    # Сохраняем покупку
    purchase_id = add_purchase(user_id, operator['name'], operator['price'])
    
    # Уведомляем администратора
    admin_markup = InlineKeyboardMarkup()
    admin_markup.add(InlineKeyboardButton(
        "Понял", 
        callback_data=f"admin_ack_{purchase_id}"
    ))
    
    price_info = f"на {operator['price']} USDT" if operator['price'] > 0 else "(договорная цена)"
    
    bot.send_message(
        ADMIN_ID,
        f"Новый заказ на подпись сим\n\n"
        f"Пользователь: @{call.from_user.username or 'нет юзернейма'}\n"
        f"ID: {user_id}\n"
        f"Оператор: {operator['name']}\n"
        f"Цена: {price_info}\n"
        f"Время: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"Свяжитесь с пользователем для выдачи",
        reply_markup=admin_markup
    )
    
    # Подтверждение пользователю
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Вернуться в меню", callback_data="back_to_menu"))
    
    # Удаляем сообщение с фото, если оно было
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    bot.send_message(
        user_id,
        f"Заказ на подпись {operator['name']} принят\n\n"
        f"Администратор свяжется с вами в ближайшее время",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_ack_"))
def admin_acknowledge(call):
    """Админ подтверждает, что понял"""
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Это не для вас")
        return
    
    purchase_id = call.data.split("_")[2]
    
    bot.answer_callback_query(call.id, "Принято")
    bot.edit_message_text(
        call.message.text + "\n\n✅ Администратор принял заказ",
        call.message.chat.id,
        call.message.message_id
    )

# ---------- ЗАПУСК БОТА ----------
if __name__ == "__main__":
    # Запускаем поток с автопроверкой платежей
    payment_thread = threading.Thread(target=check_payments_loop, daemon=True)
    payment_thread.start()
    
    # Запускаем бота
    logging.info("Бот запущен...")
    bot.infinity_polling()