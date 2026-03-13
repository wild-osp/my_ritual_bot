import os
import asyncio
import logging
import base64
from aiogram import Bot, Dispatcher, F, types as tg_types
from aiogram.filters import Command
from openai import AsyncOpenAI
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

# Настройка клиента для работы с Gemini через OpenRouter
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("GEMINI_API_KEY"), # Сюда вставь ключ от OpenRouter
)

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("✅ Nano Banana через OpenRouter готова к работе! Пришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Обхожу блокировки... Nano Banana обрабатывает фото.")
    
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # Запрос именно к модели Google Gemini через посредника
        response = await client.chat.completions.create(
            model="google/gemini-flash-1.5",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Ritual retouch: extract person, neutral grey background, formal grey shirt, black mourning ribbon in corner."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        },
                    ],
                }
            ],
        )
        
        await message.answer(f"✨ Ответ от Gemini (через прокси):\n\n{response.choices[0].message.content}")
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer(f"❌ Даже через прокси возникла ошибка: {e}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
