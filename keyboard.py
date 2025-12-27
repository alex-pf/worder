from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

import config
'''
# Динамическая клавиатура
def get_keyboard(user_id):
    buttons = [['Start', 'Next', 'Stop']]
    if user_id in config.ADMIN_IDS:
        buttons.append(['Add picture'])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
'''

# Возможные состояния (константы)
STATE_IDLE = 'idle'
STATE_GAME = 'playing'

def get_keyboard(user_id, state=STATE_IDLE):
    print("======Key board state=", state)
    buttons = []
    is_admin = user_id in config.ADMIN_IDS

    # Логика в зависимости от состояния
    if state == STATE_GAME:
        # В игре: Next word и Stop
        buttons.append(['Next word', 'Stop'])
    else:
        # Вне игры: Start и Weekly rate
        buttons.append(['Start', 'Weekly rate'])

    # Если админ — добавляем кнопку в новый ряд
    if is_admin:
        buttons.append(['Add word'])

    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)
