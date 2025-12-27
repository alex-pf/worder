import sqlite3
import logging
from datetime import datetime

DB_NAME = "worder_base.db"

def add_column_if_not_exists(cursor, table, column, definition):
    """
    Безопасно добавляет колонку в таблицу. 
    Если колонка уже существует, SQLite выбросит ошибку, которую мы игнорируем.
    """
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        logging.info(f"Database migration: Column '{column}' added to table '{table}'.")
    except sqlite3.OperationalError:
        # Колонка уже существует, ничего делать не нужно
        pass

def init_db():
    """Инициализация базы данных и применение миграций."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # 1. Создание таблицы пользователей (если нет)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at DATETIME
            )
        ''')
        
        # 2. Создание базовой таблицы попыток (если нет)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                word TEXT,
                is_correct BOOLEAN,
                created_at DATETIME
            )
        ''')

        # 3. МИГРАЦИИ (Добавление новых полей в существующую базу без потери данных)
        # Эти строки гарантируют, что у всех пользователей будут нужные колонки
        add_column_if_not_exists(cursor, "attempts", "is_first_attempt", "BOOLEAN DEFAULT 1")
        add_column_if_not_exists(cursor, "attempts", "attempt_type", "TEXT")
        
        conn.commit()

def register_user(user_id, username, first_name):
    """Регистрация нового пользователя или обновление существующего."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, joined_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, datetime.now()))
        conn.commit()

def log_attempt(user_id, word, is_correct, is_first, attempt_type):
    """Запись каждой попытки ответа в историю."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO attempts (user_id, word, is_correct, is_first_attempt, attempt_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, word, int(is_correct), int(is_first), attempt_type, datetime.now()))
        conn.commit()

def get_best_know_today(user_id):
    """
    Считает лучший результат 'You Know' (правильно с первого раза) 
    за текущие календарные сутки.
    """
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Выбираем только те записи, где ответ верный И попытка была первой за сегодня
        cursor.execute('''
            SELECT COUNT(*) 
            FROM attempts 
            WHERE user_id = ? 
            AND is_correct = 1 
            AND is_first_attempt = 1 
            AND date(created_at, 'localtime') = date('now', 'localtime')
        ''', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0

def get_user_stats(user_id):
    """
    (Дополнительно) Получение краткой статистики пользователя за всё время.
    Может пригодиться для личного кабинета.
    """
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                COUNT(*) as total, 
                SUM(is_correct) as correct 
            FROM attempts WHERE user_id = ?
        ''', (user_id,))
        return cursor.fetchone()

def get_weekly_stats(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Выбираем дату и количество правильных ответов за последние 7 дней
        cursor.execute('''
            SELECT 
                DATE(created_at) as date, 
                COUNT(*) as count 
            FROM attempts 
            WHERE user_id = ? 
              AND is_correct = 1 
              AND created_at >= DATE('now', '-7 days')
            GROUP BY date
            ORDER BY date DESC
        ''', (user_id,))
        return cursor.fetchall()
