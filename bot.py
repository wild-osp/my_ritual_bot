import os
import asyncio
import logging
import base64
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Настройка логирования для отслеживания этапов
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# Инициализация
bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

# Клиент OpenRouter (совместим с форматом OpenAI)
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1", 
    api_key=os.getenv("OPENROUTER_KEY")
)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("✅ **Бот запущен.**\nПришлите фото человека, и я создам качественный портрет на сером фоне.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    status_msg = await message.answer("⌛ Анализирую фото...")
    
    try:
        # 1. Получаем фото и кодируем в Base64 для передачи в Gemini
        file = await bot.get_file(message.photo[-1].file_id)
        file_content = await bot.download_file(file.file_path)
        image_bytes = file_content.getvalue()
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        # 2. Анализ внешности через Gemini 2.0 Flash
        logger.info("Отправка в Gemini для анализа...")
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe the person's face, hair, and age. Max 10 words."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ]
        )
        
        prompt_desc = analysis.choices[0].message.content.strip()
        logger.info(f"Описание: {prompt_desc}")
        
        await status_msg.edit_text(f"🎨 Генерирую портрет: {prompt_desc}...")

        # 3. Генерация изображения через SDXL (OpenRouter)
        # Используем b64_json, чтобы получить саму картинку сразу в коде
        logger.info("Запуск генерации в SDXL...")
        gen_response = await client.images.generate(
            model="stabilityai/stable-diffusion-xl",
            prompt=f"Professional photorealistic memorial portrait of {prompt_desc}, black formal suit, neutral grey background, studio lighting, 8k resolution",
            response_format="b64_json"
        )

        # 4. Декодируем и отправляем в Telegram
        image_data = base64.b64decode(gen_response.data[0].b64_json)
        result_file = BufferedInputFile(image_data, filename="portrait.jpg")

        await bot.send_photo(
            chat_id=message.chat.id,
            photo=result_file,
            caption=f"✨ Готово!\n\n_Анализ:_ {prompt_desc}"
        )
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await status_msg.edit_text("❌ Ошибка при обработке. Проверьте баланс в OpenRouter или попробуйте другое фото.")

async def main():
    logger.info("Старт...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
