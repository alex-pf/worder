import sqlite3
import logging

DB_NAME = "worder_base.db"


def add_column_if_not_exists(cursor, table, column, definition):
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        logging.info(f"Migration: Column '{column}' added to table '{table}'.")
    except sqlite3.OperationalError:
        pass


def init_db():
    """Инициализация структуры и применение миграций."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()

        # Таблица пользователей
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

        # Таблица попыток
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

        # Миграции (новые поля для старых баз)
        add_column_if_not_exists(cursor, "attempts", "is_first_attempt", "BOOLEAN DEFAULT 1")
        add_column_if_not_exists(cursor, "attempts", "attempt_type", "TEXT")
        # Новое поле: время напоминания (по умолчанию 18:00)
        add_column_if_not_exists(cursor, "users", "reminder_time", "TEXT DEFAULT '18:00'")

        conn.commit()
