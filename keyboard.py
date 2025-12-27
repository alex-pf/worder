from telegram import ReplyKeyboardMarkup
import config

# Возможные состояния (константы)
STATE_IDLE = 'idle'
STATE_GAME = 'playing'


def get_keyboard(user_id, state=STATE_IDLE):
    buttons = []
    is_admin = user_id in config.ADMIN_IDS

    # 1. ОБЫЧНЫЕ КНОПКИ (для всех)
    if state == STATE_GAME:
        # В игре только управление процессом
        buttons.append(['Next word', 'Stop'])
    else:
        # Вне игры только старт и статистика
        buttons.append(['Start', 'Weekly rate'])

    # 2. АДМИН-КНОПКИ
    if is_admin:
        # Создаем ряд для админских кнопок
        admin_row = ['Add word']

        # Добавляем кнопки управления рассылкой только в режиме покоя
        if state == STATE_IDLE:
            admin_row.append('Send global reminder')
            # Кнопка 'Set reminder' теперь тоже только здесь
            admin_row.append('Set reminder')

        buttons.append(admin_row)

    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

