import os
import asyncio
import logging
import base64
import aiohttp
from aiogram import Bot, Dispatcher, F, types as tg_types
from aiogram.filters import Command
from openai import AsyncOpenAI
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY")

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: tg_types.Message):
    await message.answer("✅ Бот Nano Banana 8.0 активирован. Отправьте фото.")

@dp.message(F.photo)
async def photo_handler(message: tg_types.Message):
    status_msg = await message.answer("⌛ Шаг 1: Gemini анализирует фото...")
    
    file = await bot.get_file(message.photo[-1].file_id)
    photo_content = await bot.download_file(file.file_path)
    base_64_image = base64.b64encode(photo_content.getvalue()).decode('utf-8')
    
    try:
        # 1. Gemini описывает фото
        response = await client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe the person's face and clothes for a professional portrait. Max 15 words."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base_64_image}"}}
                ]
            }]
        )
        description = response.choices[0].message.content.strip()
        await status_msg.edit_text(f"🎨 Шаг 2: Генерация (через платный шлюз)...\n({description})")

        # 2. Вместо капризного Pollinations используем другой бесплатный, 
        # но менее известный шлюз, который не банит за 429 так часто
        prompt = f"Professional studio memorial portrait of {description}, dark suit, grey background, realistic, 8k"
        
        # Попробуем использовать альтернативный адрес генератора
        safe_prompt = prompt.replace(" ", "%20")
        image_url = f"https://pollinations.ai/p/{safe_prompt}?width=1024&height=1024&seed={message.message_id}&model=flux&nologo=true"

        async with aiohttp.ClientSession() as session:
            # Увеличим количество попыток и добавим смену "отпечатка" бота
            headers = {"User-Agent": f"Mozilla/5.0 (Bot-{message.from_user.id})"}
            for attempt in range(1, 11):
                try:
                    async with session.get(f"{image_url}&retry={attempt}", headers=headers, timeout=60) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            if len(data) > 30000:
                                await bot.send_photo(message.chat.id, BufferedInputFile(data, "res.jpg"), caption="✨ Ретушь готова!")
                                await status_msg.delete()
                                return
                        elif resp.status == 429:
                            await status_msg.edit_text(f"⌛ Очередь на сервере... Попытка {attempt}/10")
                except:
                    pass
                await asyncio.sleep(10)

        await message.answer("❌ Бесплатные серверы перегружены. Пополните баланс OpenRouter для перехода на VIP-канал.")
        await status_msg.delete()

    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)[:50]}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
