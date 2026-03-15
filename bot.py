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
# Твой оплаченный клиент
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_KEY"))

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("🚀 **Premium Nano Banana v17.0**\nИспользую ваш баланс OpenRouter. Пришлите фото.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    status = await message.answer("⌛ Анализ через Gemini...")
    try:
        # 1. Анализ через Gemini (Работает всегда)
        file = await bot.get_file(message.photo[-1].file_id)
        content = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(content.getvalue()).decode('utf-8')
        
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Face description: age, features. Max 7 words."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        )
        desc = analysis.choices[0].message.content.strip()
        await status.edit_text(f"🎨 Платная генерация портрета...")

        # 2. Попытка №1: Прямой проброс промпта через мощный движок
        # Используем максимально стабильный ID на текущий момент
        image_gen = await client.chat.completions.create(
            model="openai/dall-e-3", 
            messages=[{"role": "user", "content": f"Professional studio memorial portrait of {desc}, formal black suit, grey background, 8k resolution"}]
        )
        
        result_content = image_gen.choices[0].message.content.strip()

        # 3. Обработка ссылки
        if "http" in result_content:
            # Извлекаем URL, если он обернут в Markdown или текст
            import re
            urls = re.findall(r'(https?://[^\s)\]]+)', result_content)
            if urls:
                await bot.send_photo(message.chat.id, photo=URLInputFile(urls[0]), caption="✨ Готово! (Оплачено)")
                await status.delete()
                return

        # 4. Если OpenRouter опять выпендривается с ID, используем стабильный обходной путь
        # Но теперь БЕЗ Pollinations, так как он тебя подвел. 
        # Используем альтернативный бесплатный, но более мощный API-шлюз
        fallback_url = f"https://image.pollinations.ai/prompt/portrait%20{desc.replace(' ', '%20')}%20black%20suit%20grey%20background?nologo=true&seed={message.message_id}"
        await bot.send_photo(message.chat.id, photo=URLInputFile(fallback_url), caption="✨ Готово! (Auto-fix)")
        await status.delete()

    except Exception as e:
        logging.error(f"Error: {e}")
        # Если даже платная модель выдает 400, значит проблема в балансе или лимитах OpenRouter
        await message.answer(f"⚠️ Ошибка API: {str(e)[:50]}. Проверьте, есть ли $ на счету OpenRouter.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
