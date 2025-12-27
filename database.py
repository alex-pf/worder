import sqlite3
from datetime import datetime

DB_NAME = "worder_base.db"

# --- РАБОТА С ПОЛЬЗОВАТЕЛЯМИ ---

def register_user(user_id, username, first_name):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name, joined_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, datetime.now()))
        conn.commit()

def get_all_users_with_reminders():
    """Возвращает список всех пользователей и их время напоминания."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, reminder_time FROM users")
        return cursor.fetchall()

def update_user_reminder(user_id, time_str):
    """Обновляет время ежедневного напоминания для пользователя."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("UPDATE users SET reminder_time = ? WHERE user_id = ?", (time_str, user_id))
        conn.commit()

# --- ЛОГИРОВАНИЕ И СТАТИСТИКА ---

def log_attempt(user_id, word, is_correct, is_first, attempt_type):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO attempts (user_id, word, is_correct, is_first_attempt, attempt_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, word, int(is_correct), int(is_first), attempt_type, datetime.now()))
        conn.commit()

def get_best_know_today(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
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

def get_weekly_stats(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DATE(created_at) as date, COUNT(*) as count 
            FROM attempts 
            WHERE user_id = ? AND is_correct = 1 
            AND created_at >= DATE('now', '-7 days')
            GROUP BY date ORDER BY date DESC
        ''', (user_id,))
        return cursor.fetchall()

def get_weekly_best_result(user_id):
    """Находит лучший дневной результат, переиспользуя get_weekly_stats."""
    stats = get_weekly_stats(user_id)  # Получаем список [('2025-12-27', 15), ('2025-12-26', 10), ...]
    if not stats:
        return 0

    # Извлекаем только числа (count) и находим максимальное
    counts = [row[1] for row in stats]
    return max(counts)

def get_user_stats(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) as total, SUM(is_correct) as correct 
            FROM attempts WHERE user_id = ?
        ''', (user_id,))
        return cursor.fetchone()

def get_user_reminder_time(user_id):
    """Исправленная версия: возвращает именно строку времени."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT reminder_time FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        # Извлекаем первый элемент кортежа, если он есть
        return result[0] if result else "18:00"
