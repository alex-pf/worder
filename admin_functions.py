import os
import uuid
from fuzzywuzzy import fuzz
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes



import word_manager
import config

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
