import sqlite3
import datetime

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect('gkey_market.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0,
            purchases_count INTEGER DEFAULT 0,
            registered_at TEXT
        )
    ''')
    
    # Таблица покупок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            operator TEXT,
            amount REAL,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            admin_notified INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица инвойсов для автопроверки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            invoice_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'active',
            created_at TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def get_user(user_id):
    """Получить данные пользователя"""
    conn = sqlite3.connect('gkey_market.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_balance(user_id, amount):
    """Обновить баланс пользователя"""
    conn = sqlite3.connect('gkey_market.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def add_purchase(user_id, operator, amount):
    """Добавить запись о покупке"""
    conn = sqlite3.connect('gkey_market.db')
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO purchases (user_id, operator, amount, created_at, admin_notified)
        VALUES (?, ?, ?, ?, 0)
    ''', (user_id, operator, amount, now))
    purchase_id = cursor.lastrowid
    cursor.execute('UPDATE users SET purchases_count = purchases_count + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    return purchase_id

def save_invoice(invoice_id, user_id, amount):
    """Сохранить инвойс в БД"""
    conn = sqlite3.connect('gkey_market.db')
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    cursor.execute('''
        INSERT OR REPLACE INTO invoices (invoice_id, user_id, amount, status, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (invoice_id, user_id, amount, 'active', now))
    conn.commit()
    conn.close()

def update_invoice_status(invoice_id, status):
    """Обновить статус инвойса"""
    conn = sqlite3.connect('gkey_market.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE invoices SET status = ? WHERE invoice_id = ?', (status, invoice_id))
    conn.commit()
    conn.close()

def get_active_invoices():
    """Получить все активные инвойсы"""
    conn = sqlite3.connect('gkey_market.db')
    cursor = conn.cursor()
    cursor.execute('SELECT invoice_id, user_id, amount FROM invoices WHERE status = "active"')
    invoices = cursor.fetchall()
    conn.close()
    return invoices