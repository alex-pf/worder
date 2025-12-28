import os
from openai import OpenAI
import config
from pydub import AudioSegment, effects

client = OpenAI(api_key=config.OPENAI_API_KEY)

async def transcribe_voice(file_path):
    try:
        with open(file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                language="en",
                # Промпт дает ИИ контекст, что говорит ребенок, и снижает строгость к грамматике
                prompt="The speaker is a child learning English. Focus on the target word, ignore stutters or slight mispronunciations."
            )
        # Убираем пунктуацию и приводим к нижнему регистру
        return transcript.text.lower().strip().replace('.', '').replace('!', '').replace('?', '')
    except Exception as e:
        print(f"DEBUG: Ошибка ИИ: {e}")
        return None


async def generate_speech(text, output_path):
    """Генерирует громкое эталонное произношение с паузами."""
    try:
        temp_speech = output_path + "_raw.mp3"

        # 1. Генерируем голос (выбрали Nova для энергии)
        response = client.audio.speech.create(
            model="tts-1",
            voice="fable",
            input=text
        )
        response.stream_to_file(temp_speech)

        # 2. Обработка через pydub
        audio = AudioSegment.from_file(temp_speech)

        # --- УСИЛЕНИЕ ЗВУКА ---
        # Способ А: Просто прибавить Дб (например, +10 Дб)
        audio = audio + 20
        print("========> +20 децибел\n")
        # Способ Б: Нормализация (выравнивание до максимума без искажений)
        #audio = effects.normalize(audio)
        # ----------------------

        # Добавляем тишину
        one_sec_silence = AudioSegment.silent(duration=1000)
        final_audio = one_sec_silence + audio + one_sec_silence

        # Экспортируем с повышенным битрейтом для четкости
        final_audio.export(output_path, format="mp3", bitrate="192k")

        if os.path.exists(temp_speech):
            os.remove(temp_speech)
        return True
    except Exception as e:
        print(f"DEBUG: Ошибка TTS: {e}")
        return False