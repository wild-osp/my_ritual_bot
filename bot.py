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

# Ключи из твоих переменных
bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()
# Твой оплаченный клиент
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_KEY"))

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("🌟 **Премиум-бот Nano Banana активен.**\nТеперь мы используем ваш оплаченный баланс для генерации через SDXL (без сбоев).")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    status = await message.answer("⌛ Анализируем черты лица...")
    try:
        # 1. Скачиваем фото
        file = await bot.get_file(message.photo[-1].file_id)
        content = await bot.download_file(file.file_path)
        base64_img = base64.b64encode(content.getvalue()).decode('utf-8')
        
        # 2. Анализ через Gemini (Тут твои деньги уже работают)
        analysis = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Describe age, gender, hair, glasses. Max 10 words."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]}]
        )
        desc = analysis.choices[0].message.content.strip()
        await status.edit_text(f"🎨 Генерируем премиум-портрет через SDXL...")

        # 3. ГЕНЕРАЦИЯ ЧЕРЕЗ ТВОЙ ОПЛАЧЕННЫЙ OPENROUTER
        # Мы просим модель вернуть прямую ссылку на готовую картинку
        image_gen = await client.chat.completions.create(
            model="stabilityai/sdxl", # Это надежная платная модель
            messages=[{
                "role": "user", 
                "content": f"Professional studio memorial portrait of {desc}, wearing a black suit, grey background, 8k, realistic."
            }]
        )
        
        # OpenRouter для SDXL часто возвращает ссылку в тексте или в поле 'url'
        image_url = image_gen.choices[0].message.content.strip()
        
        # Если модель вернула markdown-ссылку ![image](http...), вырезаем чистый URL
        if "http" in image_url:
            clean_url = image_url.split("http")[-1].split(")")[0].split("]")[0].strip()
            clean_url = "http" + clean_url
            
            await bot.send_photo(message.chat.id, photo=URLInputFile(clean_url), caption="✨ Готово! (Оплачено через OpenRouter)")
        else:
            await message.answer("❌ Модель не смогла создать ссылку. Попробуйте еще раз.")
        
        await status.delete()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer(f"❌ Произошла ошибка: {str(e)[:50]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
