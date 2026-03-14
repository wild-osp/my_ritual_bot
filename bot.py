import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types as tg_types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
load_dotenv()

# Инициализируем официальный клиент Google
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("✅ Бот Nano Banana (Official Google API) запущен!\nСервер в Нидерландах готов к работе. Пришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Изучаю лицо через Gemini Vision...")
    
    try:
        # Скачиваем фото из Telegram в память
        file = await bot.get_file(message.photo[-1].file_id)
        photo_stream = await bot.download_file(file.file_path)
        image_bytes = photo_stream.getvalue()
        
        # 1. Анализируем фото через Gemini 2.0 Flash
        vision_response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                'Describe the face and hair of this person very precisely but briefly. Max 20 words. No punctuation.'
            ]
        )
        person_desc = vision_response.text.strip()
        
        await status_msg.edit_text("⌛ Шаг 2: Рисую портрет через Google Imagen 3...")

        # 2. Формируем промпт для генератора картинок Imagen 3
        prompt = (f"A highly detailed, professional memorial portrait photo of {person_desc}, "
                  f"wearing a formal grey shirt. The background is a clean neutral studio grey. "
                  f"There is a black diagonal mourning ribbon in the bottom right corner. "
                  f"Hyperrealistic, 8k resolution, soft cinematic lighting.")

        # Генерируем изображение через официальную модель Google Imagen
        image_response = client.models.generate_images(
            model='imagen-3.0-generate-001',
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/jpeg",
                aspect_ratio="1:1"
            )
        )
        
        # 3. Достаем готовую картинку из ответа и отправляем в Telegram
        generated_image_bytes = image_response.generated_images[0].image.image_bytes
        photo_file = BufferedInputFile(generated_image_bytes, filename="retouch.jpg")
        
        await bot.send_photo(message.chat.id, photo=photo_file, caption="✨ Мемориальная ретушь (Google Imagen 3) готова!")
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Ошибка Google API: {e}")
        error_text = str(e)[:200]
        await message.answer(f"❌ Произошла ошибка на стороне серверов Google: {error_text}\nВозможно, ключ не активирован для Imagen.")

async def main():
    logging.info("🚀 Бот (Official API) запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
