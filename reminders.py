import database
import os
from draw_rate import generate_motivation_image
from telegram.ext import ContextTypes


async def send_daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_id = job.user_id

    # 1. Считаем рекорд, переиспользуя существующую логику
    best_rate = database.get_weekly_best_result(user_id)

    # 2. Генерируем картинку через DALL-E
    image_url = await generate_motivation_image()

    message = (
        f"🌟 *Time to practice!*\n"
        f"Your best result this week is *{best_rate}* words in one day. "
        f"Can you beat it today? 💪"
    )

    try:
        if image_url:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=image_url,
                caption=message,
                parse_mode='Markdown'
            )
        else:
            await context.bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')
    except Exception as e:
        print(f"DEBUG: Failed to remind user {user_id}: {e}")


def setup_reminders(application):
    """Вызывается при старте бота для загрузки всех напоминаний из БД"""
    users = database.get_all_users_with_reminders()
    for user_id, time_str in users:
        schedule_user_reminder(application.job_queue, user_id, time_str)


def schedule_user_reminder(job_queue, user_id, time_str):
    # Удаляем старые задачи этого пользователя, если они были
    current_jobs = job_queue.get_jobs_by_name(f"remind_{user_id}")
    for job in current_jobs:
        job.schedule_removal()

    # Парсим время
    h, m = map(int, time_str.split(':'))

    # Планируем задачу
    job_queue.run_daily(
        send_daily_reminder,
        time=datetime.time(hour=h, minute=m),  # Это время по умолчанию UTC
        user_id=user_id,
        name=f"remind_{user_id}"
    )
    print(f"DEBUG: Reminder for {user_id} scheduled at {time_str} UTC")
