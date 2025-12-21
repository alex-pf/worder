import os
import config
import random

def get_unique_words():
    """
    Считывает файлы из папки и возвращает список уникальных слов.
    Поддерживает форматы: 'слово-индекс.png' и 'слово.png'
    """
    words = set()
    if not os.path.exists(config.IMAGE_DIR):
        print(f"Ошибка: Папка {config.IMAGE_DIR} не найдена!")
        return []

    for filename in os.listdir(config.IMAGE_DIR):
        if filename.lower().endswith(".png"):
            # Убираем расширение .png
            name_without_ext = filename.rsplit('.', 1)[0]
            
            # Если есть дефис, берем часть до него, если нет — всё имя файла
            if '-' in name_without_ext:
                word = name_without_ext.split('-')[0].lower().strip()
            else:
                word = name_without_ext.lower().strip()
            
            words.add(word)
    
    return sorted(list(words))

def get_random_image_for_word(word):
    """
    Находит все картинки для слова и выбирает одну случайную.
    Ищет файлы 'word.png' или 'word-*.png'
    """
    word = word.lower()
    images = []
    
    if not os.path.exists(config.IMAGE_DIR):
        return None

    for f in os.listdir(config.IMAGE_DIR):
        if not f.lower().endswith(".png"):
            continue
            
        name_without_ext = f.rsplit('.', 1)[0].lower()
        
        # Условие: имя файла это точно 'слово' ИЛИ начинается на 'слово-'
        if name_without_ext == word or name_without_ext.startswith(f"{word}-"):
            images.append(f)

    if not images:
        return None
        
    return os.path.join(config.IMAGE_DIR, random.choice(images))

# Инициализируем список слов
KNOWN_WORDS = get_unique_words()
