import os
import asyncio
import base64
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv

# Настройка логов
logging.basicConfig(level=logging.INFO)
load_dotenv()

# Конфигурация
API_KEY = os.getenv("OPENROUTER_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def openrouter_request(model, messages=None, prompt=None, is_image_gen=False):
    """Универсальная функция для запросов к OpenRouter"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Если генерируем картинку, меняем URL и структуру (для SDXL через Chat API или Image API)
    # Но надежнее использовать текстовое описание лица через Gemini, а затем SDXL
    data = {
        "model": model,
        "messages": messages if messages else [{"role": "user", "content": prompt}]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as resp:
            return await resp.json()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("📸 Отправьте фото для создания ритуального портрета.")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    status = await message.answer("⏳ Обработка...")
    
    try:
        # 1. Качаем фото
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)
        base64_image = base64.b64encode(file_bytes.getvalue()).decode('utf-8')

        # 2. Анализ лица (Gemini 2.0 Flash)
        await status.edit_text("🔍 Анализирую черты лица...")
        analysis_data = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe face, hair and age of this person. Max 10 words."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post("https://openrouter.ai/api/v1/chat/completions", 
                                   headers={"Authorization": f"Bearer {API_KEY}"}, 
                                   json=analysis_data) as resp:
                res = await resp.json()
                description = res['choices'][0]['message']['content']

        # 3. Генерация портрета (SDXL)
        await status.edit_text(f"🎨 Рисую портрет: {description}...")
        
        # Для генерации картинок на OpenRouter через SDXL используем правильный эндпоинт
        gen_url = "https://openrouter.ai/api/v1/images/generations"
        gen_data = {
            "model": "stabilityai/stable-diffusion-xl",
            "prompt": f"Professional photorealistic studio portrait of {description}, wearing black suit, neutral grey background, high resolution, 8k",
            "response_format": "b64_json"
        }

        async with session.post(gen_url, headers={"Authorization": f"Bearer {API_KEY}"}, json=gen_data) as resp:
            gen_res = await resp.json()
            if 'error' in gen_res:
                raise Exception(gen_res['error']['message'])
            
            image_b64 = gen_res['data'][0]['b64_json']
            image_data = base64.b64decode(image_b64)

        # 4. Отправка
        await bot.send_photo(
            message.chat.id, 
            BufferedInputFile(image_data, filename="res.jpg"),
            caption="✅ Портрет готов"
        )
        await status.delete()

    except Exception as e:
        logging.error(e)
        await status.edit_text(f"❌ Ошибка: {str(e)}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
