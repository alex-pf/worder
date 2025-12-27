import os
import uuid
import random
from fuzzywuzzy import fuzz
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from keyboard import get_keyboard
from handlers import send_next_word, reset_inactivity_timer, stop_inactivity_timer, finish_game, get_weekly_rate

import word_manager
import voice_service
import config
import database


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
        os.rename(path, os.path.join(config.IMAGE_DIR, f"{word}-{len(exist) + 1}.png"))
        word_manager.KNOWN_WORDS = word_manager.get_unique_words()
        user_data['awaiting_admin_action'] = None
        await update.message.reply_text(f"Saved {word}!", reply_markup=get_keyboard(user_id))
        return

    if text == "Start":
        print("\n\n Start ==> \n")
        user_data['know_count'] = user_data['learned_count'] = 0
        w = list(word_manager.KNOWN_WORDS);
        random.shuffle(w)
        user_data.update({'words': w, 'current_index': 0, 'game_active': True})
        await send_next_word(update, context)
    elif text == "Stop":
        print("\n\n Stop ==> \n")
        await finish_game(update, context) #if user_data.get('game_active') else None

    elif text == "Weekly rate":
        await get_weekly_rate(update, context)
    elif text == "Add picture" and user_id in config.ADMIN_IDS:
        user_data['awaiting_admin_action'] = 'send_photo'
        await update.message.reply_text("Send me new picture.")
    elif text == "Next word" and user_data.get('game_active'):
        print("\n\n Next ==> \n")
        user_data['current_index'] += 1;
        await send_next_word(update, context)
    elif user_data.get('game_active'):
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
            await update.message.reply_text("Correct! ✅");
            await send_next_word(update, context)
        else:
            user_data['is_first_attempt'] = False
            await update.message.reply_text("Wrong!");
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
