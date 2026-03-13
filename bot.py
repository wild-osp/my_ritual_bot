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
    api_key=os.getenv("GEMINI_API_KEY"),
)

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("✅ Бот ритуальной ретуши Nano Banana активен!\nПришлите фото, и я создам мемориальный портрет.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ черт лица...")
    
    # Скачиваем фото
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # 1. Gemini анализирует лицо (просим очень кратко, чтобы не превысить лимиты текста)
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this person's facial features and hair very briefly for a realistic portrait recreation. Max 60 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }]
        )
        
        person_desc = analysis.choices[0].message.content
        await status_msg.edit_text("⌛ Шаг 2: Генерация портрета (DALL-E 3)...")

        # 2. Генерация изображения по описанию
        # Используем DALL-E 3 для максимального сходства и качества
        prompt = (
            f"A high-quality hyper-realistic memorial portrait of {person_desc}. "
            f"The person is wearing a clean formal grey shirt. "
            f"Background is a neutral professional studio grey. "
            f"A black diagonal mourning ribbon is in the bottom right corner. "
            f"Soft cinematic lighting, professional photography, 8k resolution."
        )

        image_response = await client.images.generate(
            model="openai/dall-e-3",
            prompt=prompt,
            size="1024x1024"
        )

        image_url = image_response.data[0].url
        
        # 3. Отправка результата
        await bot.send_photo(
            message.chat.id, 
            photo=image_url, 
            caption="✅ Ретушь выполнена нейросетью Nano Banana."
        )
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Ошибка в процессе: {e}")
        # Обрезаем текст ошибки до 400 символов, чтобы не упасть при отправке в Telegram
        safe_error_message = str(e)[:400]
        await message.answer(f"❌ Произошла ошибка: {safe_error_message}\n\nПроверьте баланс на OpenRouter.")

async def main():
    logging.info("🚀 Бот запущен через OpenRouter...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
