#import os
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
            dates.append(day.strftime('%d %b'))  # Формат "27 Dec"
            counts.append(date_map.get(day_str, 0))

        date_start, date_end = dates[0], dates[-1]
        max_score = max(counts) if counts else 0  # Находим лучший результат

        # 2. GPT-4o → ГЕНЕРАЦИЯ SVG
        svg_prompt = f"""
        Generate a professional SVG vertical bar chart.
        User: {user_name}
        Best Result: {max_score} words
        Period: {date_start} - {date_end}
        Data: {counts}
        Labels: {dates}

        Rules:
        - ViewBox: 0 0 600 450 (increased height for header)
        - Background: light pastel blue (#E3F2FD) with 20px rounded corners

        - HEADER LOGIC:
          * Top-left: Text "{user_name}'s Progress" (bold, size 24px)
          * Top-right: Text "Best: {max_score} words" (size 18px, color #2E7D32)
          * Subtitle: "{date_start} - {date_end}" below the name (size 14px, gray color)

        - CHART LOGIC:
          * Bars: use vibrant orange (#FF9800) or teal (#009688)
          * Heights: bars MUST be exactly proportional to values {counts}
          * Values: show the numeric value above each bar (size 16px)
          * X-axis: show dates below each bar (size 12px)

        - Style: clean, modern, flat design. No grid lines.
        - Return ONLY valid SVG code starting with <svg and ending with </svg>
        """

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": svg_prompt}],
            temperature=0.2
        )

        raw_content = completion.choices[0].message.content.strip()

        # Очистка и конвертация (как в предыдущем коде)
        start_idx = raw_content.find("<svg")
        end_idx = raw_content.rfind("</svg>")
        if start_idx != -1 and end_idx != -1:
            svg_code = raw_content[start_idx: end_idx + 6]
        else:
            return None

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            cairosvg.svg2png(bytestring=svg_code.encode('utf-8'), write_to=tmp.name)
            png_path = tmp.name

        return png_path

    except Exception as e:
        print(f"DEBUG: Error in draw_rate: {e}")
        return None
