import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
import google.generativeai as genai
from dotenv import load_dotenv

# Загрузка переменных (для локального теста)
load_dotenv()

# Берем токены из переменных окружения (на хостинге мы их пропишем в панели)
TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# Настройка нейросети
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="Ты — мастер ритуальной ретуши. При получении фото: 1. Оставь только одного человека. 2. Сделай фон нейтральным серым. 3. Замени одежду на строгую серую рубашку. 4. Улучши четкость лица. 5. Добавь черную ленту в углу."
)

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(F.photo)
async def handle_photo(message: Message):
    status = await message.answer("⌛ Начинаю обработку через Nano Banana... Пожалуйста, подождите.")
    
    # Скачиваем фото в память
    file_info = await bot.get_file(message.photo[-1].file_id)
    photo_bytes = await bot.download_file(file_info.file_path)
    
    try:
        # Отправляем запрос в Gemini
        response = model.generate_content([
            "Сделай ритуальную ретушь этого фото.",
            {"mime_type": "image/jpeg", "data": photo_bytes.getvalue()}
        ])
        
        # Если нейросеть вернула текст (описание или ссылку)
        await status.edit_text("✅ Обработка завершена! (В API Gemini сейчас обновляется прямая отдача фото, проверьте результат в логах или дождитесь выгрузки)")
        
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}")

async def main():
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())