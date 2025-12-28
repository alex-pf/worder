import os
import uuid
import random
from datetime import datetime, timezone
from fuzzywuzzy import fuzz
from telegram import Update
from telegram.ext import ContextTypes
from keyboard import get_keyboard, STATE_GAME, STATE_IDLE
from handlers import send_next_word, reset_inactivity_timer, stop_inactivity_timer, finish_game, get_weekly_rate
import reminders  # Импортируем новый модуль напоминаний

import word_manager
import voice_service
from draw_rate import generate_motivation_image
import config
import database


# --- ОБРАБОТКА ТЕКСТА И ГОЛОСА ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, user_id, user_data = update.message.text, update.effective_user.id, context.user_data
    is_admin = user_id in config.ADMIN_IDS

    if text == config.ADMIN_SECRET_CODE:
        config.ADMIN_IDS.add(user_id)
        await update.message.reply_text("Admin mode ON!", reply_markup=get_keyboard(user_id))
        return

    # --- ЛОГИКА АДМИН-ПАНЕЛИ (НАПОМИНАНИЯ) ---
    if is_admin:
        # Добавим принт, чтобы видеть в консоли, что админ что-то нажал
        print(f"DEBUG: Admin {user_id} sent text: {text}")
        if text == "Send global reminder":
            # 1. Сначала уведомляем админа, что процесс пошел (генерация DALL-E занимает 10 сек)
            status_msg = await update.message.reply_text("🎨 Generating motivation image and sending to all users...")

            # 2. Генерируем одну общую картинку для рассылки
            image_url = await generate_motivation_image()  # или из draw_rate, смотря где она у вас

            users = database.get_all_users_with_reminders()
            success_count = 0
            # ОТЛАДКА: Считаем количество записей в полученном списке
            total_users_in_db = len(users)
            print(f"DEBUG: Starting global reminder. Total users found in DB: {total_users_in_db}")

            # 3. Рассылаем всем
            for uid, _ in users:
                try:
                    print("DEBUG: Sending global reminder to {uid}")
                    # Для каждого считаем его личный рекорд
                    best_rate = database.get_weekly_best_result(uid)
                    message = (
                        f"🚀 *Let's play!*\n"
                        f"Your best result this week is *{best_rate}* words.\n"
                        f"Ready to learn something new today? 💪"
                    )

                    if image_url:
                        await context.bot.send_photo(
                            chat_id=uid,
                            photo=image_url,
                            caption=message,
                            parse_mode='Markdown'
                        )
                    else:
                        await context.bot.send_message(uid, message, parse_mode='Markdown')

                    success_count += 1
                except Exception as e:
                    print(f"DEBUG: Failed to send global reminder to {uid}: {e}")
                    continue

            # 4. Удаляем временный статус и пишем отчет админу
            await status_msg.delete()
            await update.message.reply_text(f"✅ Successfully sent to {success_count} users.")
            return

        if text == "Set reminder":
            try:
                # Получаем время из базы
                current_time = database.get_user_reminder_time(user_id)
                # Получаем текущее время UTC (стандарт 2025 года)
                server_now = datetime.now(timezone.utc).strftime("%H:%M")

                await update.message.reply_text(
                    f"⚙️ *Admin: Reminder Setup*\n\n"
                    f"Current time in DB: `{current_time}` (UTC)\n"
                    f"Current server time: `{server_now}` (UTC)\n\n"
                    "To change, type:\n"
                    "`Set time HH:MM` (e.g. `Set time 15:00`)",
                    parse_mode='Markdown'
                )
            except Exception as e:
                # Если здесь случится ошибка (например, NameError), бот не упадет,
                # а просто выведет ошибку в консоль сервера
                print(f"ERROR in Set reminder: {e}")
            return

        if text.startswith("Set time "):
            try:
                new_time_input = text.replace("Set time ", "").strip()
                # Проверка формата
                datetime.strptime(new_time_input, "%H:%M")

                database.update_user_reminder(user_id, new_time_input)
                reminders.schedule_user_reminder(context.job_queue, user_id, new_time_input)

                confirmed_time = database.get_user_reminder_time(user_id)

                await update.message.reply_text(
                    f"✅ *Success!*\n"
                    f"Database updated to: `{confirmed_time}` (UTC)",
                    parse_mode='Markdown'
                )
            except ValueError:
                await update.message.reply_text("❌ Error! Use format HH:MM")
            except Exception as e:
                print(f"ERROR in Set time: {e}")
            return

    # --- ЛОГИКА АДМИН-ДЕЙСТВИЙ (СЛОВА) ---
    if user_data.get('awaiting_admin_action') == 'send_word':
        word = text.lower().strip()
        path = user_data.get('temp_admin_photo')
        exist = [f for f in os.listdir(config.IMAGE_DIR) if f.startswith(f"{word}-") or f == f"{word}.png"]
        os.rename(path, os.path.join(config.IMAGE_DIR, f"{word}-{len(exist) + 1}.png"))
        word_manager.KNOWN_WORDS = word_manager.get_unique_words()
        user_data['awaiting_admin_action'] = None
        await update.message.reply_text(f"Saved {word}!", reply_markup=get_keyboard(user_id))
        return

    # --- ИГРОВАЯ ЛОГИКА ---
    if text == "Start":
        user_data['know_count'] = user_data['learned_count'] = 0
        w = list(word_manager.KNOWN_WORDS)
        random.shuffle(w)
        user_data.update({'words': w, 'current_index': 0, 'game_active': True, 'is_first_attempt': True})
        await send_next_word(update, context)

    elif text == "Stop":
        if user_data.get('game_active'):
            await finish_game(update, context)

    elif text == "Weekly rate":
        await get_weekly_rate(update, context)

    elif text == "Add word" and is_admin:  # Синхронизировали с текстом на кнопке
        user_data['awaiting_admin_action'] = 'send_photo'
        await update.message.reply_text("Send me a new picture.")

    elif text == "Next word" and user_data.get('game_active'):
        user_data['current_index'] += 1
        user_data['is_first_attempt'] = True
        await send_next_word(update, context)

    elif user_data.get('game_active'):
        # Логика проверки текстового ответа
        stop_inactivity_timer(user_id, context)
        correct = user_data['words'][user_data['current_index']].lower()
        is_first = user_data.get('is_first_attempt', True)
        success = text.lower().strip() == correct
        database.log_attempt(user_id, correct, success, is_first, 'text')

        if success:
            if is_first:
                user_data['know_count'] += 1
            else:
                user_data['learned_count'] += 1
            user_data['current_index'] += 1
            user_data['is_first_attempt'] = True
            await update.message.reply_text("Correct! ✅")
            await send_next_word(update, context)
        else:
            user_data['is_first_attempt'] = False
            await update.message.reply_text("Wrong! Try again or use 'Next word'")
            reset_inactivity_timer(user_id, update.effective_chat.id, context)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data, user_id = context.user_data, update.effective_user.id
    if not user_data.get('game_active'): return
    stop_inactivity_timer(user_id, context)
    f = await update.message.voice.get_file()
    path = os.path.join(config.TEMP_DIR, f"{uuid.uuid4()}.ogg")
    await f.download_to_drive(path)
    status = await update.message.reply_text("Checking... 🎤")
    rec = await voice_service.transcribe_voice(path)
    if os.path.exists(path): os.remove(path)
    if not rec:
        await status.edit_text("Error. Try again!");
        reset_inactivity_timer(user_id, update.effective_chat.id, context)
        return
    correct = user_data['words'][user_data['current_index']].lower()
    is_first = user_data.get('is_first_attempt', True)
    is_correct = fuzz.ratio(rec, correct) >= 80
    database.log_attempt(user_id, correct, is_correct, is_first, 'voice')
    if is_correct:
        if is_first:
            user_data['know_count'] += 1
        else:
            user_data['learned_count'] += 1
        await status.edit_text(f"Great! ({rec}) ✅")
        user_data['current_index'] += 1;
        await send_next_word(update, context)
    else:
        user_data['is_first_attempt'] = False
        await status.edit_text(f"I heard '{rec}', expected '{correct}'. 👇")
        tts = os.path.join(config.TEMP_DIR, f"tts_{correct}.mp3")
        if await voice_service.generate_speech(correct, tts):
            with open(tts, 'rb') as f:
                await update.message.reply_voice(f)
            if os.path.exists(tts): os.remove(tts)
        reset_inactivity_timer(user_id, update.effective_chat.id, context)
