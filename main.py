import logging
import config
import db_init
import word_manager
import reminders  # Импортируем наш модуль напоминаний
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters
from handlers import start_cmd
from msg_processing import handle_message, handle_voice
from admin_functions import handle_admin_photo

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


def main():
    """Запуск бота English for Kids."""

    # 1. Инициализация базы данных и проверка структуры
    db_init.init_db()

    # 2. Проверка загруженных слов
    print(f"Инициализация... Загружено слов: {len(word_manager.KNOWN_WORDS)}")

    # 3. Сборка приложения
    # Для JobQueue необходимо наличие библиотеки: pip install "python-telegram-bot[job-queue]"
    application = ApplicationBuilder().token(config.TOKEN).build()

    # --- НОВЫЙ БЛОК: Инициализация напоминаний ---
    # Мы передаем job_queue в функцию настройки, чтобы запланировать задачи для всех юзеров
    try:
        reminders.setup_reminders(application)
        print("Система напоминаний успешно инициализирована.")
    except Exception as e:
        print(f"Ошибка при настройке напоминаний: {e}")
    # ---------------------------------------------

    # 4. Регистрация хендлеров
    application.add_handler(CommandHandler("start", start_cmd))

    # Обработка ФОТО (Админ-панель)
    application.add_handler(MessageHandler(
        filters.PHOTO | filters.Document.IMAGE,
        handle_admin_photo
    ))

    # Обработка ГОЛОСА (Игра)
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))

    # Обработка ТЕКСТА (Кнопки, пароли, ответы)
    application.add_handler(MessageHandler(
        filters.TEXT & (~filters.COMMAND),
        handle_message
    ))

    print("Бот запущен. Ожидание сообщений...")

    # Запуск цикла опроса API
    application.run_polling(
        poll_interval=config.POLL_INTERVAL,
        timeout=config.POLL_TIMEOUT
    )


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем.")
    except Exception as e:
        print(f"\nКритическая ошибка при запуске: {e}")
