import os
import asyncio
import logging
import base64
import urllib.parse
import re
from aiogram import Bot, Dispatcher, F, types as tg_types
from aiogram.filters import Command
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
load_dotenv()

# Инициализация клиента для Gemini (OpenRouter)
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("GEMINI_API_KEY"),
)

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("✅ Nano Banana готова!\nПришлите фото для мемориальной ретуши.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Анализ черт лица...")
    
    # Получаем фото
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # 1. Анализ лица через Gemini
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe the person's face and hair very briefly. No punctuation, no new lines. Max 10 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }]
        )
        
        person_desc = analysis.choices[0].message.content
        await status_msg.edit_text("⌛ Шаг 2: Генерация портрета...")

        # 2. Жёсткая очистка текста для URL
        # Убираем всё, кроме латинских букв и пробелов
        clean_desc = re.sub(r'[^a-zA-Z\s]', '', person_desc)
        clean_desc = clean_desc.replace('\n', ' ').strip()
        
        # 3. Формируем финальный промпт для Pollinations
        final_prompt = (f"memorial portrait of {clean_desc} "
                        f"wearing formal grey shirt grey background "
                        f"black mourning ribbon bottom right hyperrealistic 8k")
        
        encoded_prompt = urllib.parse.quote(final_prompt)
        
        # Используем модель Flux, убираем логотип и задаем уникальный seed
        image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed={message.message_id}&model=flux&nologo=true"

        # 4. Отправляем результат напрямую через URL
        # Telegram сам скачает картинку со своих серверов
        try:
            await bot.send_photo(
                message.chat.id, 
                photo=image_url, 
                caption="✨ Ретушь готова!\n\n(Если картинка не загрузилась сразу, подождите пару секунд)"
            )
        except Exception as e:
            logging.error(f"Telegram Photo Error: {e}")
            await message.answer(f"🔗 Ссылка на вашу ретушь:\n{image_url}")

        await status_msg.delete()
        
    except Exception as e:
        logging.error(f"Общая ошибка: {e}")
        await message.answer("❌ Не удалось обработать фото. Попробуйте еще раз.")

async def main():
    logging.info("🚀 Бот запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
