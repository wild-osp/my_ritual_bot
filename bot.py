import os
import asyncio
import logging
import base64
import urllib.parse
import aiohttp
from aiogram import Bot, Dispatcher, F, types as tg_types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiogram.types import BufferedInputFile

logging.basicConfig(level=logging.INFO)

# --- НАСТРОЙКИ ---
# Вставь свой токен Телеграм и ключ OpenRouter прямо сюда для теста
TELEGRAM_TOKEN = "ТВОЙ_ТОКЕН_ТЕЛЕГРАМ"
OPENROUTER_KEY = "sk-or-v1-ТВОЙ_КЛЮЧ_OPENROUTER" 

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("🍌 Nano Banana готова к тесту! Пришли фото.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ через OpenRouter...")
    
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base_64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # Анализ Gemini
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Describe age, hair color and face briefly. Max 10 words."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
            ]}]
        )
        desc = response.choices[0].message.content
        await status_msg.edit_text(f"⌛ Шаг 2: Рисую (ожидание до 60с)...\nОписание: {desc}")

        # Промпт для рисования
        prompt = f"Professional memorial portrait of {desc}, grey shirt, studio background, mourning ribbon, 8k"
        url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1024&height=1024&nologo=true&model=flux&seed={message.message_id}"

        # Умный сканер картинки (ждем пока нарисует)
        async with aiohttp.ClientSession() as session:
            for i in range(12):
                async with session.get(url) as r:
                    data = await r.read()
                    if len(data) > 40000: # Если это не логотип
                        await bot.send_photo(message.chat.id, BufferedInputFile(data, "r.jpg"), caption="✨ Готово!")
                        await status_msg.delete()
                        return
                await asyncio.sleep(5)
        
        await message.answer("❌ Сервер занят, попробуйте еще раз.")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer(f"❌ Ошибка API: {str(e)[:50]}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
