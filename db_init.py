import sqlite3
import logging

DB_NAME = "worder_base.db"


def add_column_if_not_exists(cursor, table, column, definition):
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        logging.info(f"Migration: Column '{column}' added to table '{table}'.")
    except sqlite3.OperationalError:
        pass


def migrate_old_users(cursor):
    """
    Находит всех уникальных пользователей в таблице attempts,
    которых еще нет в таблице users, и регистрирует их.
    """
    try:
        # INSERT OR IGNORE гарантирует, что мы не создадим дубликатов
        # Мы берем только user_id, остальные поля (username, name)
        # заполнятся автоматически, когда пользователь нажмет /start в будущем.
        cursor.execute('''
                       INSERT
                       OR IGNORE INTO users (user_id, joined_at, reminder_time)
                       SELECT DISTINCT user_id, '2025-12-28 00:00:00', '18:00'
                       FROM attempts
                       ''')
        affected = cursor.rowcount
        if affected > 0:
            logging.info(f"Migration: {affected} old users migrated from attempts to users table.")
    except sqlite3.OperationalError as e:
        logging.error(f"Migration error (migrate_old_users): {e}")


def init_db():
    """Инициализация базы данных и применение миграций."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()

        # 1. Создание таблицы пользователей
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS users
                       (
                           user_id
                           INTEGER
                           PRIMARY
                           KEY,
                           username
                           TEXT,
                           first_name
                           TEXT,
                           joined_at
                           DATETIME
                       )
                       ''')

        # 2. Создание таблицы попыток
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS attempts
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           user_id
                           INTEGER,
                           word
                           TEXT,
                           is_correct
                           BOOLEAN,
                           created_at
                           DATETIME
                       )
                       ''')

        # 3. МИГРАЦИИ СТРУКТУРЫ
        add_column_if_not_exists(cursor, "attempts", "is_first_attempt", "BOOLEAN DEFAULT 1")
        add_column_if_not_exists(cursor, "attempts", "attempt_type", "TEXT")
        add_column_if_not_exists(cursor, "users", "reminder_time", "TEXT DEFAULT '18:00'")

        # 4. МИГРАЦИЯ ДАННЫХ (Восстановление пользователей из истории)
        migrate_old_users(cursor)

        conn.commit()
