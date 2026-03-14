import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types as tg_types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from google import genai
from google.genai import types
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

# Официальный клиент Google
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("✅ Бот Nano Banana переключен на стабильную версию 1.5 Flash!\nПришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ лица (Gemini 1.5 Flash)...")
    
    try:
        file = await bot.get_file(message.photo[-1].file_id)
        photo_stream = await bot.download_file(file.file_path)
        image_bytes = photo_stream.getvalue()
        
        # 1. Используем СТАБИЛЬНУЮ модель 1.5 Flash вместо 2.0
        vision_response = client.models.generate_content(
            model='gemini-1.5-flash', # Поменяли версию здесь
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                'Describe face features, age and hair color briefly. Max 15 words.'
            ]
        )
        person_desc = vision_response.text.strip()
        
        await status_msg.edit_text("⌛ Шаг 2: Генерация через Imagen 3...")

        # 2. Промпт для Imagen
        prompt = (f"A professional memorial portrait of {person_desc}, "
                  f"wearing a formal grey shirt, neutral studio grey background, "
                  f"black diagonal mourning ribbon in bottom right corner, 8k resolution.")

        # Генерируем изображение
        image_response = client.models.generate_images(
            model='imagen-3.0-generate-001',
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/jpeg"
            )
        )
        
        generated_image_bytes = image_response.generated_images[0].image.image_bytes
        photo_file = BufferedInputFile(generated_image_bytes, filename="retouch.jpg")
        
        await bot.send_photo(message.chat.id, photo=photo_file, caption="✨ Ретушь готова!")
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Ошибка API: {e}")
        # Если ошибка в квотах, выводим понятное сообщение
        if "429" in str(e):
            await message.answer("⚠️ Google временно ограничил лимиты. Пожалуйста, подождите 1 минуту и попробуйте снова.")
        elif "imagen" in str(e).lower():
            await message.answer("❌ Вашему аккаунту Google AI Studio еще не разрешено генерировать картинки. Обычно доступ открывается через пару часов после создания ключа.")
        else:
            await message.answer(f"❌ Ошибка: {str(e)[:150]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
