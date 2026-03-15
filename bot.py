import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types

logging.basicConfig(level=logging.INFO)

# ВСТАВЬ ТОКЕН СЮДА ДЛЯ ПРОВЕРКИ
TOKEN = "ТВОЙ_ТОКЕН"

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message()
async def any_msg(message: types.Message):
    print(f"ПОЛУЧЕНО: {message.text}") # Это отобразится в логах
    await message.answer("Я тебя вижу!")

async def main():
    # Эта строка ВАЖНА: она выгоняет всех "зависших" ботов
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
