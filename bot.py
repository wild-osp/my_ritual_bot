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
from dotenv import load_dotenv

# Загружаем переменные из настроек Bothost
load_dotenv()

logging.basicConfig(level=logging.INFO)

# --- ДАННЫЕ АВТОРИЗАЦИИ ---
# Токен берем из настроек хостинга (проверь, что он там есть!)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
# Ключ OpenRouter оставляем вшитым, раз он верный
OPENROUTER_KEY = "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"

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

# Проверка токена перед запуском
if not TELEGRAM_TOKEN or ":" not in TELEGRAM_TOKEN:
    logging.error("❌ ОШИБКА: TELEGRAM_TOKEN не задан или неверный в настройках Bothost!")
    exit()

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("🚀 Бот запущен! Жду фото для мемориальной ретуши.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализирую фото...")
    
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base_64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # 1. Описание через Gemini
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe face and hair color briefly. Max 10 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        
        person_desc = response.choices[0].message.content.strip()
        await status_msg.edit_text(f"⌛ Шаг 2: Создаю портрет...\n({person_desc})")

        # 2. Генерация
        prompt = (f"A professional memorial studio portrait of {person_desc}, "
                  f"wearing a formal grey shirt, neutral studio grey background, "
                  f"a black diagonal mourning ribbon in the bottom right corner, 8k.")
        
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&model=flux&seed={message.message_id}"

        # 3. Ожидание чистого фото без логотипа
        async with aiohttp.ClientSession() as session:
            for attempt in range(1, 15):
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        if len(data) > 40000:
                            await bot.send_photo(message.chat.id, BufferedInputFile(data, "r.jpg"), caption="✨ Ретушь готова!")
                            await status_msg.delete()
                            return
                await asyncio.sleep(5)

        await message.answer("❌ Не удалось получить фото от сервера. Попробуйте еще раз.")
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:100]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
