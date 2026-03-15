import os
import asyncio
import logging
import base64
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import URLInputFile
from openai import AsyncOpenAI
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv()

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()
# Используем твой оплаченный OpenRouter
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1", 
    api_key=os.getenv("OPENROUTER_KEY"),
    timeout=30.0 # Чтобы бот не зависал дольше 30 секунд
)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("✅ Бот запущен. Пришлите фото для обработки.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    status = await message.answer("⌛ Работаю (Gemini анализирует лицо)...")
    try:
        # 1. Получаем описание через Gemini
        file = await bot.get_file(message.photo[-1].file_id)
        content = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(content.getvalue()).decode('utf-8')
        
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Short description of person: age, glasses, hair. Max 5 words."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        )
        desc = analysis.choices[0].message.content.strip()
        
        await status.edit_text(f"🎨 Создаю портрет (модель FLUX)...")

        # 2. Генерируем картинку. 
        # ВНИМАНИЕ: Используем модель 'google/gemini-2.0-flash-001' для генерации промпта,
        # а саму картинку тянем через проверенный Pollinations, но БЕЗ падений.
        
        image_url = f"https://image.pollinations.ai/prompt/Professional%20studio%20portrait%20of%20{desc.replace(' ', '%20')}%20wearing%20black%20suit%20grey%20background%20high%20quality?nologo=true&seed={message.message_id}"

        # 3. Отправляем
        await bot.send_photo(
            message.chat.id, 
            photo=URLInputFile(image_url), 
            caption=f"✨ Готово!\nОписание: {desc}"
        )
        await status.delete()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("⚠️ Произошла заминка. Попробуйте еще раз через минуту.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
