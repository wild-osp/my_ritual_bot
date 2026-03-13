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

# Инициализация клиента OpenRouter
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("GEMINI_API_KEY"), # Убедись, что тут ключ от OpenRouter (sk-or-v1-...)
)

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("✅ Бот Nano Banana (Gemini) запущен через OpenRouter!\nПришлите фото для ритуальной ретуши.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Связываюсь с нейросетью... Пробую доступные модели.")
    
    # 1. Скачиваем фото из Telegram
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    # 2. Список моделей для перебора (OpenRouter часто меняет их доступность)
    models_to_try = [
        "google/gemini-2.0-flash-001",    # Самая новая и быстрая
        "google/gemini-flash-1.5",        # Стандартная Nano Banana
        "google/gemini-2.0-flash-exp:free" # Бесплатная экспериментальная
    ]
    
    final_response = None
    
    try:
        for model_id in models_to_try:
            try:
                logging.info(f"🔄 Попытка через модель: {model_id}")
                
                response = await client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text", 
                                    "text": "Memorial portrait retouch task: Extract the person, place on a neutral studio grey background, change clothes to a formal grey shirt, add a black diagonal mourning ribbon in the bottom right corner. Describe the result."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                                },
                            ],
                        }
                    ],
                    timeout=30.0
                )
                
                if response and response.choices[0].message.content:
                    final_response = response.choices[0].message.content
                    logging.info(f"✅ Успех с моделью: {model_id}")
                    break # Выходим из цикла, если получили ответ
                    
            except Exception as e:
                logging.warning(f"⚠️ Модель {model_id} недоступна: {e}")
                continue # Пробуем следующую

        # 3. Выдача результата пользователю
        if final_response:
            await message.answer(f"✨ **Результат обработки:**\n\n{final_response}", parse_mode="Markdown")
        else:
            await message.answer("❌ К сожалению, все доступные модели Gemini на OpenRouter сейчас выдали ошибку. Проверьте баланс/лимиты аккаунта OpenRouter.")
            
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        await message.answer(f"💥 Произошла системная ошибка: {e}")

async def main():
    logging.info("🚀 Бот запущен и готов к работе!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
