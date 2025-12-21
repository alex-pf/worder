import os
import uuid
import random
from fuzzywuzzy import fuzz
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

import word_manager
import voice_service
import config
import database

# Динамическая клавиатура
def get_keyboard(user_id):
    buttons = [['Start', 'Next', 'Stop']]
    if user_id in config.ADMIN_IDS:
        buttons.append(['Add picture'])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# --- ТАЙМЕРЫ ---
async def timeout_callback(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_data = context.application.user_data.get(job.user_id)
    if user_data and user_data.get('game_active'):
        user_data['game_active'] = False
        await context.bot.send_message(
            chat_id=job.chat_id, 
            text="⌛ Lesson stopped due to inactivity.",
            reply_markup=get_keyboard(job.user_id)
        )

def reset_inactivity_timer(user_id, chat_id, context: ContextTypes.DEFAULT_TYPE):
    stop_inactivity_timer(user_id, context)
    context.job_queue.run_once(timeout_callback, config.INACTIVITY_TIMEOUT, chat_id=chat_id, user_id=user_id, name=str(user_id))

def stop_inactivity_timer(user_id, context: ContextTypes.DEFAULT_TYPE):
    current_jobs = context.job_queue.get_jobs_by_name(str(user_id))
    for job in current_jobs: job.schedule_removal()

# --- ОСНОВНАЯ ЛОГИКА ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    database.register_user(user.id, user.username, user.first_name)
    await update.message.reply_text(f"Hi {user.first_name}!", reply_markup=get_keyboard(user.id))

async def finish_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data, user_id = context.user_data, update.effective_user.id
    know, learned = user_data.get('know_count', 0), user_data.get('learned_count', 0)
    user_data['game_active'] = False
    stop_inactivity_timer(user_id, context)
    
    best = database.get_best_know_today(user_id)
    msg = f"🏁 Done!\n⭐ You know: {know}\n📖 You learned: {learned}\n🏆 Best today: {max(best, know)}"
    await update.message.reply_text(msg, reply_markup=get_keyboard(user_id))
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
                await update.message.reply_photo(f, caption=f"{stats}\nWhat is this?", reply_markup=get_keyboard(update.effective_user.id))
            reset_inactivity_timer(update.effective_user.id, update.effective_chat.id, context)
    else: await finish_game(update, context)

# --- АДМИН ПАНЕЛЬ ---
async def process_and_check_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo: return None
    photo = update.message.photo[-1]
    if photo.file_size > 1 * 1024 * 1024:
        await update.message.reply_text("Error: File > 1MB")
        return None
    path = os.path.join(config.TEMP_DIR, f"admin_{uuid.uuid4()}.png")
    f = await photo.get_file()
    await f.download_to_drive(path)
    return path

async def handle_admin_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    print("DEBUG: Получено фото!") 
    user_id, user_data = update.effective_user.id, context.user_data
    if user_id not in config.ADMIN_IDS: return

    path = await process_and_check_photo(update, context)
    if not path: return

    # Сценарий 1: Фото + Подпись
    if update.message.caption:
        word = update.message.caption.lower().strip()
        try:
            exist = [f for f in os.listdir(config.IMAGE_DIR) if f.startswith(f"{word}-") or f == f"{word}.png"]
            final = os.path.join(config.IMAGE_DIR, f"{word}-{len(exist)+1}.png")
            os.rename(path, final)
            word_manager.KNOWN_WORDS = word_manager.get_unique_words()
            await update.message.reply_text(f"Word '{word}' added! ✅")
        except Exception as e: await update.message.reply_text(f"Error: {e}")
    # Сценарий 2: Только фото
    else:
        user_data['temp_admin_photo'], user_data['awaiting_admin_action'] = path, 'send_word'
        await update.message.reply_text("Photo saved! Now send the word.")

# --- ОБРАБОТКА ТЕКСТА И ГОЛОСА ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, user_id, user_data = update.message.text, update.effective_user.id, context.user_data
    
    if text == config.ADMIN_SECRET_CODE:
        config.ADMIN_IDS.add(user_id)
        await update.message.reply_text("Admin mode ON!", reply_markup=get_keyboard(user_id))
        return

    if user_data.get('awaiting_admin_action') == 'send_word':
        word = text.lower().strip()
        path = user_data.get('temp_admin_photo')
        exist = [f for f in os.listdir(config.IMAGE_DIR) if f.startswith(f"{word}-") or f == f"{word}.png"]
        os.rename(path, os.path.join(config.IMAGE_DIR, f"{word}-{len(exist)+1}.png"))
        word_manager.KNOWN_WORDS = word_manager.get_unique_words()
        user_data['awaiting_admin_action'] = None
        await update.message.reply_text(f"Saved {word}!", reply_markup=get_keyboard(user_id))
        return

    if text == "Start":
        user_data['know_count'] = user_data['learned_count'] = 0
        w = list(word_manager.KNOWN_WORDS); random.shuffle(w)
        user_data.update({'words': w, 'current_index': 0, 'game_active': True})
        await send_next_word(update, context)
    elif text == "Stop": await finish_game(update, context) if user_data.get('game_active') else None
    elif text == "Add picture" and user_id in config.ADMIN_IDS:
        user_data['awaiting_admin_action'] = 'send_photo'
        await update.message.reply_text("Send photo.")
    elif text == "Next" and user_data.get('game_active'):
        user_data['current_index'] += 1; await send_next_word(update, context)
    elif user_data.get('game_active'):
        stop_inactivity_timer(user_id, context)
        correct = user_data['words'][user_data['current_index']].lower()
        is_first = user_data.get('is_first_attempt', True)
        success = text.lower().strip() == correct
        database.log_attempt(user_id, correct, success, is_first, 'text')
        if success:
            if is_first: user_data['know_count'] += 1
            else: user_data['learned_count'] += 1
            user_data['current_index'] += 1
            await update.message.reply_text("Correct! ✅"); await send_next_word(update, context)
        else:
            user_data['is_first_attempt'] = False
            await update.message.reply_text("Wrong!"); reset_inactivity_timer(user_id, update.effective_chat.id, context)

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
        await status.edit_text("Error. Try again!"); reset_inactivity_timer(user_id, update.effective_chat.id, context)
        return
    correct = user_data['words'][user_data['current_index']].lower()
    is_first = user_data.get('is_first_attempt', True)
    is_correct = fuzz.ratio(rec, correct) >= 80
    database.log_attempt(user_id, correct, is_correct, is_first, 'voice')
    if is_correct:
        if is_first: user_data['know_count'] += 1
        else: user_data['learned_count'] += 1
        await status.edit_text(f"Great! ({rec}) ✅")
        user_data['current_index'] += 1; await send_next_word(update, context)
    else:
        user_data['is_first_attempt'] = False
        await status.edit_text(f"I heard '{rec}', expected '{correct}'. 👇")
        tts = os.path.join(config.TEMP_DIR, f"tts_{correct}.mp3")
        if await voice_service.generate_speech(correct, tts):
            with open(tts, 'rb') as f: await update.message.reply_voice(f)
            if os.path.exists(tts): os.remove(tts)
        reset_inactivity_timer(user_id, update.effective_chat.id, context)
