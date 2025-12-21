import logging
import config
import database
import word_manager
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters
from handlers import handle_message, handle_voice, start_cmd, handle_admin_photo

# Настройка логирования для отладки в консоли
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def main():
    """Запуск бота English for Kids."""
    
    # Инициализация базы данных и проверка структуры
    database.init_db()
    
    # Проверка загруженных слов
    print(f"Инициализация... Загружено слов: {len(word_manager.KNOWN_WORDS)}")

    # Сборка приложения
    # ВАЖНО: Просто .build(). Очередь задач (JobQueue) подключится автоматически, 
    # если установлена библиотека: pip install "python-telegram-bot[job-queue]"
    application = ApplicationBuilder().token(config.TOKEN).build()

    # 1. Команда старт
    application.add_handler(CommandHandler("start", start_cmd))

    # 2. Обработка ФОТО (Админ-панель)
    # Ставим ВЫШЕ текстового обработчика. 
    # Добавлен фильтр для документов, если фото отправлено без сжатия.
    application.add_handler(MessageHandler(
        filters.PHOTO | filters.Document.IMAGE, 
        handle_admin_photo
    ))

    # 3. Обработка ГОЛОСА (Игра)
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))

    # 4. Обработка ТЕКСТА (Кнопки, пароли, ответы)
    # Фильтр ~filters.COMMAND игнорирует сообщения, начинающиеся с '/'
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
