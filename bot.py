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

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("GEMINI_API_KEY"),
)

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("✅ Бот ритуальной ретуши готов! Пришлите фото, и я создам портрет.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ лица...")
    
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # 1. Gemini анализирует фото и создает описание для генератора
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this person's face in detail for high-quality recreation. Focus on age, hair, and features. Output ONLY the description."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }]
        )
        
        person_desc = analysis.choices[0].message.content
        await status_msg.edit_text("⌛ Шаг 2: Генерация ретушированного портрета...")

        # 2. Генерируем новое изображение (используем OpenAI DALL-E 3 через OpenRouter)
        # Если на балансе OpenRouter нет средств, используй бесплатную модель "google/gemini-2.0-pro-exp-02-05:free"
        image_response = await client.images.generate(
            model="openai/dall-e-3", 
            prompt=f"A hyper-realistic memorial portrait of {person_desc}. The person is wearing a clean formal grey shirt. Neutral studio grey background. A black diagonal mourning ribbon is in the bottom right corner. Soft studio lighting, 8k resolution, professional photography.",
            size="1024x1024"
        )

        image_url = image_response.data[0].url
        
        # 3. Отправляем готовое фото
        await bot.send_photo(message.chat.id, photo=image_url, caption="✅ Ретушь готова!")
        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer(f"❌ Ошибка генерации: {e}\n(Убедитесь, что на OpenRouter есть баланс для DALL-E 3)")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
