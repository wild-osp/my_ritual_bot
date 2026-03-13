import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types as tg_types
from aiogram.filters import Command
from google import genai
from google.genai import types as genai_types
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
load_dotenv()

# Ключи (должны быть прописаны в панели Bothost)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Инициализация клиента с явным указанием стабильной версии API v1
client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options={'api_version': 'v1'}
)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("✅ Бот ритуальной ретуши активен! Пришлите фото, и я опишу необходимые правки (подготовка к генерации).")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Фото получено. Связываюсь с нейросетью Gemini 1.5 Flash...")
    
    # 1. Получаем файл из Telegram
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    
    try:
        # 2. Формируем части запроса
        prompt_text = (
            "Ritual retouch task: extract the person from the photo. "
            "Place them on a neutral professional studio grey background. "
            "Change their clothes to a formal grey shirt. "
            "Add a black diagonal mourning ribbon in the bottom right corner. "
            "Keep the face features realistic and sharp."
        )
        
        prompt_part = genai_types.Part.from_text(text=prompt_text)
        image_part = genai_types.Part.from_bytes(
            data=photo_content.getvalue(), 
            mime_type="image/jpeg"
        )

        # 3. Отправляем запрос (используем Content объект для исключения ошибок валидации)
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=[
                genai_types.Content(
                    role="user", 
                    parts=[prompt_part, image_part]
                )
            ]
        )
        
        # 4. Выдаем результат
        if response.text:
            await message.answer(f"✨ **Анализ ретуши выполнен:**\n\n{response.text}", parse_mode="Markdown")
        else:
            await message.answer("Нейросеть обработала изображение, но не смогла сформулировать ответ.")
            
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Ошибка Gemini: {e}")
        await message.answer(f"❌ Ошибка: {e}")

async def main():
    logging.info("🚀 Сброс вебхуков и запуск Polling...")
    # Очищаем старые сообщения, чтобы бот не завис
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
