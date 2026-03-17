import os
import asyncio
import logging
import base64
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import URLInputFile
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Настройка логов, чтобы видеть всё в консоли панели
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
load_dotenv()

# Инициализация
bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()
# Клиент для работы с твоим оплаченным балансом
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1", 
    api_key=os.getenv("OPENROUTER_KEY"),
    timeout=30.0
)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("✅ **Бот Ritual Retouch готов!**\n\nПришлите фото человека, и я создам профессиональный портрет в черном костюме.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    # Отправляем временный статус
    status = await message.answer("⌛ Анализирую черты лица...")
    
    try:
        # 1. Скачиваем фото и конвертируем в Base64 для Gemini
        file = await bot.get_file(message.photo[-1].file_id)
        content = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(content.getvalue()).decode('utf-8')
        
        # 2. Описание через Gemini (используем твой баланс OpenRouter)
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Describe age, hair style, glasses, and facial expression. 7 words max. Be precise."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        )
        description = response.choices[0].message.content.strip()
        logging.info(f"Описание: {description}")

        await status.edit_text("🎨 Генерирую портрет в костюме...")

        # 3. Формируем ссылку для генерации (безопасно кодируем промпт)
        # Добавляем seed, чтобы каждая генерация была уникальной
        import urllib.parse
        clean_desc = urllib.parse.quote(description)
        image_url = f"https://image.pollinations.ai/prompt/Professional%20studio%20portrait%20of%20{clean_desc}%20wearing%20formal%20black%20suit%20grey%20background%208k%20highly%20detailed?nologo=true&seed={message.message_id}"

        # 4. Отправляем результат пользователю
        await bot.send_photo(
            message.chat.id, 
            photo=URLInputFile(image_url), 
            caption=f"✨ Портрет готов!\n\n**Описание:** {description}"
        )
        await status.delete()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await status.edit_text("⚠️ Ошибка при обработке. Попробуйте другое фото через минуту.")

async def main():
    # Очищаем очередь старых сообщений, чтобы бот не "захлебнулся"
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
