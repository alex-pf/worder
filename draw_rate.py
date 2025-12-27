import os
import tempfile
import cairosvg
from datetime import datetime, timedelta
from openai import OpenAI
import config

client = OpenAI(api_key=config.OPENAI_API_KEY)

async def generate_funny_chart_image(stats_data, user_name):
    png_path = None
    try:
        # 1. ПОДГОТОВКА ДАННЫХ
        today = datetime.now().date()
        date_map = {date_str: count for date_str, count in stats_data}
        counts, dates = [], []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_str = day.strftime('%Y-%m-%d')
            dates.append(day_str)
            counts.append(date_map.get(day_str, 0))

        date_start, date_end = dates[0], dates[-1]

        # 2. GPT-4o → ТОЧНЫЙ КВАДРАТНЫЙ SVG
        svg_prompt = f"""
        Create a vertical bar chart SVG. 
        Data: {counts}. Dates: {dates}. 
        Title: {user_name}'s Progress.
        Rules:
        - ViewBox MUST be square: "0 0 500 500"
        - Canvas background MUST be transparent (no <rect> for background)
        - Use bright solid colors for bars
        - Text must be black or dark blue
        - Return ONLY valid SVG code
        """

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": svg_prompt}]
        )

        raw_content = completion.choices[0].message.content.strip()

        # Очистка кода
        start_idx = raw_content.find("<svg")
        end_idx = raw_content.rfind("</svg>")
        if start_idx != -1 and end_idx != -1:
            svg_code = raw_content[start_idx: end_idx + 6]
        else:
            svg_code = raw_content.replace("```svg", "").replace("```", "").strip()

        # 3. КОНВЕРТАЦИЯ В PNG (RGBA по умолчанию)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            cairosvg.svg2png(bytestring=svg_code.encode('utf-8'), write_to=tmp.name)
            png_path = tmp.name

        # 4. DALL-E 2 → СТИЛИЗАЦИЯ (LEGO)
        # Мы отправляем PNG с альфа-каналом. DALL-E перерисует его в Lego-стиле.
        with open(png_path, "rb") as image_file:
            response = client.images.edit(
                model="dall-e-2",
                image=image_file,
                prompt=(
                    f"Add a Lego cartoon style background for the bar chart."
                    f"It should be scene of lego mini-figures fight with inglish words."
                    f"Add happy Lego mini-figures on tops of the bars."
                    f"Don't change original bar chart at all. Only resize it to fit to 1024x1024."
                ),
                n=1,
                size="1024x1024"
            )
        return response.data[0].url

    except Exception as e:
        print(f"DEBUG: Error in draw_rate: {e}")
        return None
    finally:
        # Чистим временный файл
        if png_path and os.path.exists(png_path):
            try:
                os.remove(png_path)
            except:
                pass

'''
f"Transform this chart into a professional 3D Lego cartoon style. "
                    f"Bars are stacks of colorful Lego bricks. "
                    f"Add happy Lego mini-figures on top of the bars. "
                    f"Background is a blurred playful Lego room. "
                    f"Vibrant Pixar lighting, high quality render."
'''