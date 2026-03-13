import os
import asyncio
import logging
import base64
from aiogram import Bot, Dispatcher, F, types as tg_types
from aiogram.filters import Command
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
load_dotenv()

# Инициализация клиента OpenRouter (обход блокировок Google)
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("GEMINI_API_KEY"), # Твой API ключ от OpenRouter
)

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("✅ Nano Banana (Gemini) через OpenRouter запущена!\nПришлите фото для ретуши.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Связываюсь с сервером... Обработка фото.")
    
    # 1. Скачиваем фото из Telegram
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    
    # 2. Кодируем в Base64
    base64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # 3. Запрос к Gemini через OpenRouter
        # Используем точный ID модели, который не выдает 404
        response = await client.chat.completions.create(
            model="google/gemini-flash-1.5-8b", 
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "Memorial portrait retouch: extract the person, place on a neutral professional studio grey background, change clothes to a formal grey shirt, add a black mourning ribbon in the bottom right corner. Describe the final look."
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        },
                    ],
                }
            ],
        )
        
        # 4. Отправляем результат
        result_text = response.choices[0].message.content
        await message.answer(f"✨ **Результат анализа Gemini:**\n\n{result_text}", parse_mode="Markdown")
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Ошибка OpenRouter: {e}")
        await message.answer(f"❌ Ошибка при обращении к модели: {e}")

async def main():
    logging.info("🚀 Запуск бота через OpenRouter...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
