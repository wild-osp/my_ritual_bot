import os
import asyncio
import logging
import base64
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Настройка логов
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# Инициализация бота и клиента
bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1", 
    api_key=os.getenv("OPENROUTER_KEY")
)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("🕯 **Бот для ритуальной ретуши готов.**\nПришлите фото человека, и я создам профессиональный портрет на сером фоне в черном костюме.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    status_msg = await message.answer("⌛ Анализирую черты лица...")
    
    try:
        # 1. Скачиваем фото и кодируем в Base64 для Gemini
        file = await bot.get_file(message.photo[-1].file_id)
        file_content = await bot.download_file(file.file_path)
        image_bytes = file_content.getvalue()
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        # 2. Анализ через Gemini 2.0 Flash
        logger.info("Отправка фото на анализ в Gemini...")
        analysis_response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this person's face for a portrait generator. Mention age, hair style, facial hair, and glasses if present. Be concise (10 words max)."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ]
        )
        
        description = analysis_response.choices[0].message.content.strip()
        logger.info(f"Описание получено: {description}")
        
        await status_msg.edit_text(f"🎨 Генерирую портрет для: {description}...")

        # 3. Генерация изображения через SDXL на OpenRouter
        # Мы запрашиваем b64_json, чтобы получить картинку прямо в ответе
        logger.info("Запуск генерации в SDXL...")
        gen_response = await client.images.generate(
            model="stabilityai/stable-diffusion-xl",
            prompt=f"Professional studio memorial portrait of {description}, wearing formal black suit, solid neutral grey background, high resolution, photorealistic, 8k, sharp focus, cinematic lighting",
            size="1024x1024",
            response_format="b64_json"
        )

        # 4. Декодируем картинку из ответа
        raw_image_data = base64.b64decode(gen_response.data[0].b64_json)
        final_photo = BufferedInputFile(raw_image_data, filename="result.jpg")

        # 5. Отправка результата пользователю
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=final_photo,
            caption=f"✨ **Результат готов**\n\n_Параметры лица:_ {description}"
        )
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Произошла ошибка: {e}", exc_info=True)
        await status_msg.edit_text("❌ Произошла ошибка при обработке. Проверьте баланс OpenRouter или попробуйте другое фото.")

async def main():
    logger.info("Бот запущен...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
