#from fuzzywuzzy import fuzz
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from keyboard import get_keyboard, STATE_GAME, STATE_IDLE
from draw_rate import generate_funny_chart_image
import word_manager
import config
import database
import os

# --- ТАЙМЕРЫ ---
async def timeout_callback(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_data = context.application.user_data.get(job.user_id)
    if user_data and user_data.get('game_active'):
        user_data['game_active'] = False
        await context.bot.send_message(
            chat_id=job.chat_id, 
            text="⌛ Lesson stopped due to inactivity.",
            reply_markup=get_keyboard(job.user_id, STATE_IDLE)
        )

def reset_inactivity_timer(user_id, chat_id, context: ContextTypes.DEFAULT_TYPE):
    stop_inactivity_timer(user_id, context)
    context.job_queue.run_once(timeout_callback, config.INACTIVITY_TIMEOUT, chat_id=chat_id, user_id=user_id, name=str(user_id))

def stop_inactivity_timer(user_id, context: ContextTypes.DEFAULT_TYPE):
    print("=== stop_inactivity_timer ===")

    # Проверка, что job_queue вообще существует
    if not context.job_queue:
        print("DEBUG: JobQueue не инициализирован!")
        return

    current_jobs = context.job_queue.get_jobs_by_name(str(user_id))
    if current_jobs:
        for job in current_jobs:
            job.schedule_removal()

# --- ОСНОВНАЯ ЛОГИКА ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    database.register_user(user.id, user.username, user.first_name)
    await update.message.reply_text(f"Hi {user.first_name}!", reply_markup=get_keyboard(user.id, STATE_IDLE))

async def finish_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("=== finish_game ===")
    user_data, user_id = context.user_data, update.effective_user.id
    know, learned = user_data.get('know_count', 0), user_data.get('learned_count', 0)
    user_data['game_active'] = False
    stop_inactivity_timer(user_id, context)
    
    best = database.get_best_know_today(user_id)
    msg = f"🏁 Done!\n⭐ You know: {know}\n📖 You learned: {learned}\n🏆 Best today: {max(best, know)}"
    await update.message.reply_text(msg, reply_markup=get_keyboard(user_id, STATE_IDLE))
    user_data['know_count'], user_data['learned_count'] = 0, 0

async def send_next_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    index = user_data.get('current_index', 0)
    user_data['is_first_attempt'] = True
    if index < len(user_data.get('words', [])):
        word = user_data['words'][index]
        path = word_manager.get_random_image_for_word(word)
        stats = f"📊 K: {user_data.get('know_count', 0)} | L: {user_data.get('learned_count', 0)}"
        if path:
            with open(path, 'rb') as f:
                await update.message.reply_photo(f, caption=f"{stats}\nWhat is this?", reply_markup=get_keyboard(update.effective_user.id, STATE_GAME))
            reset_inactivity_timer(update.effective_user.id, update.effective_chat.id, context)
    else: await finish_game(update, context)


async def get_weekly_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    # 1. Получаем данные из базы
    stats = database.get_weekly_stats(user_id)

    # Если данных нет вообще, выводим только текст
    if not stats:
        await update.message.reply_text(
            "📊 *Статистика за 7 дней:*\n\nДанных пока нет. Начни заниматься, чтобы увидеть свой график!",
            parse_mode='Markdown',
            reply_markup=get_keyboard(user_id, STATE_IDLE)
        )
        return

    # 2. Информируем об ожидании (так как GPT + генерация PNG занимают 3-5 секунд)
    status_msg = await update.message.reply_text("📊 Please wait... I'm drawing your progress! 🎨")

    try:
        # 3. Генерируем график (теперь это путь к локальному PNG)
        image_result = await generate_funny_chart_image(stats, user.first_name)

        if image_result:
            # Считаем общее кол-во слов для подписи
            total_week = sum(count for date_str, count in stats)
            caption = f"🌟🌟🌟 *{user.first_name}*, here are your results for the last week! 🔥🔥🔥"

            # Проверяем, что получили: URL или путь к файлу
            if image_result.startswith("http"):
                await update.message.reply_photo(
                    photo=image_result,
                    caption=caption,
                    parse_mode='Markdown',
                    reply_markup=get_keyboard(user_id, STATE_IDLE)
                )
            else:
                with open(image_result, 'rb') as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption=caption,
                        parse_mode='Markdown',
                        reply_markup=get_keyboard(user_id, STATE_IDLE)
                    )
                # Удаляем временный файл после отправки
                if os.path.exists(image_result):
                    os.remove(image_result)
        else:
            # Если картинка не сгенерировалась, выводим хотя бы итоговую сумму
            total_week = sum(count for date_str, count in stats)
            await update.message.reply_text(
                f"Не удалось нарисовать график, но ты молодец!\n🔥 За неделю выучено слов: {total_week}",
                reply_markup=get_keyboard(user_id, STATE_IDLE)
            )

    except Exception as e:
        print(f"ERROR in get_weekly_rate: {e}")
        await update.message.reply_text("Произошла ошибка при подготовке отчета. Попробуй позже.")

    finally:
        # Удаляем "Drawing..." сообщение в любом случае
        await status_msg.delete()
