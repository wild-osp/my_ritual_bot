import os
import asyncio
import logging
import base64
import urllib.parse
import httpx
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from openai import AsyncOpenAI
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_KEY"))

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("✨ Бот активен. Пришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    status = await message.answer("⌛ Шаг 1: Анализ фото...")
    try:
        # 1. Анализ через Gemini (Работает стабильно)
        file = await bot.get_file(message.photo[-1].file_id)
        content = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(content.getvalue()).decode('utf-8')
        
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Describe the person's face: age, hair, glasses. Max 5 words. No punctuation."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        )
        desc = analysis.choices[0].message.content.strip()
        await status.edit_text(f"🎨 Шаг 2: Создание портрета...\n(Распознано: {desc})")
        
        # 2. Формируем УЛЬТРА-чистый URL без лишних параметров (?width, &model и т.д.)
        raw_prompt = f"Professional studio portrait, {desc}, wearing a formal black suit, neutral grey background, hyperrealistic"
        safe_prompt = urllib.parse.quote(raw_prompt)
        image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}"
        
        # 3. Скачиваем картинку
        async with httpx.AsyncClient(follow_redirects=True) as http_client:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            
            # Таймаут увеличен до 90 секунд, так как генерация может занять время
            response = await http_client.get(image_url, headers=headers, timeout=90.0)
            
            if response.status_code == 200:
                photo_data = BufferedInputFile(response.content, filename="portrait.jpg")
                await bot.send_photo(message.chat.id, photo=photo_data, caption="✨ Готово!")
                await status.delete()
            else:
                # Честно говорим, если бесплатный генератор снова упал
                await status.edit_text(f"❌ Сервер генерации картинок Pollinations перегружен (Ошибка {response.status_code}). Подождите 5 минут и попробуйте снова.")

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await status.edit_text("❌ Внутренняя ошибка сети. Попробуйте еще раз.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
