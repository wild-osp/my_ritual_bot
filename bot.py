import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import URLInputFile
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Включаем подробный лог, чтобы видеть каждое действие
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_KEY"))

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    logging.info(f"Получена команда /start от {message.from_user.id}")
    await message.answer("🚀 Бот ожил и готов к работе! Пришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    logging.info("Получено фото, начинаю обработку...")
    status = await message.answer("⌛ Анализирую лицо через Gemini...")
    try:
        # Устанавливаем короткий таймаут для Gemini
        file = await bot.get_file(message.photo[-1].file_id)
        content = await bot.download_file(file.file_path)
        import base64
        base64_img = base64.b64encode(content.getvalue()).decode('utf-8')
        
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Describe age, hair, glasses. 5 words max."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}],
            timeout=20.0
        )
        desc = response.choices[0].message.content.strip()
        logging.info(f"Gemini выдал описание: {desc}")

        await status.edit_text("🎨 Генерирую финальный портрет...")
        
        # Самый быстрый и надежный способ получения картинки
        prompt_escaped = desc.replace(" ", "%20")
        image_url = f"https://image.pollinations.ai/prompt/Professional%20studio%20portrait%20{prompt_escaped}%20wearing%20black%20suit%20grey%20background?nologo=true"
        
        await bot.send_photo(message.chat.id, photo=URLInputFile(image_url), caption="✨ Готово!")
        await status.delete()
        logging.info("Фото успешно отправлено!")

    except Exception as e:
        logging.error(f"Ошибка в процессе: {e}")
        await message.answer(f"❌ Произошла ошибка. Попробуйте другое фото.")

async def main():
    # ГЛАВНОЕ: Удаляем все старые сообщения, которые накопились, пока бот висел
    logging.info("Очистка очереди сообщений...")
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Запуск лонг-поллинга...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")
