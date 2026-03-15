import os
import asyncio
import logging
import base64
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
openai_client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_KEY"))

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("✨ Бот активен. Пришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    status = await message.answer("⌛ Обработка (Анализ)...")
    try:
        # 1. Скачиваем фото пользователя
        file = await bot.get_file(message.photo[-1].file_id)
        content = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(content.getvalue()).decode('utf-8')
        
        # 2. Быстрый анализ через Gemini
        analysis = await openai_client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Describe person: age, hair, glasses. 5 words max. No punctuation."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        )
        desc = analysis.choices[0].message.content.strip().replace(" ", "%20")
        
        # 3. Формируем ссылку
        image_url = f"https://image.pollinations.ai/prompt/professional%20studio%20portrait%20{desc}%20black%20suit%20grey%20background?width=1024&height=1024&model=flux&nologo=true"
        
        await status.edit_text("🎨 Генерация портрета...")

        # 4. СКАЧИВАЕМ КАРТИНКУ САМИ (Маскируемся под Chrome)
        async with httpx.AsyncClient() as http_client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = await http_client.get(image_url, headers=headers, timeout=60.0)
            
            if response.status_code == 200:
                # Переводим байты в формат для aiogram
                photo_data = BufferedInputFile(response.content, filename="portrait.jpg")
                await bot.send_photo(message.chat.id, photo=photo_data, caption="✨ Готово!")
            else:
                await message.answer(f"❌ Сервер генерации отклонил запрос (Код {response.status_code}).")

        await status.delete()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("❌ Сбой соединения. Попробуйте еще раз.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
