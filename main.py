import os
import asyncio
from collections import defaultdict

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    FSInputFile,
)
from aiogram.filters import Command
from dotenv import load_dotenv

# ================= CONFIG =================
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

BACK_BUTTON = "⬅️ Orqaga"
MAX_PENDING = 5  # bir user 5 tadan ortiq so'rov yuborsa cancel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "images")

# ================= USER TASK CONTROL =================
user_tasks = {}
user_counts = defaultdict(int)

async def run_protected(user_id, coroutine_func):
    """Per-user task protection: 5+ so'rov yuborilsa cancel qilinadi"""
    if user_id in user_tasks and not user_tasks[user_id].done():
        user_counts[user_id] += 1
        if user_counts[user_id] > MAX_PENDING:
            user_tasks[user_id].cancel()
            user_counts[user_id] = 0
            return False  # bekor qilindi
        return None  # shunchaki ignore

    user_counts[user_id] = 0
    task = asyncio.create_task(coroutine_func())
    user_tasks[user_id] = task

    try:
        await task
    except asyncio.CancelledError:
        pass
    finally:
        user_tasks.pop(user_id, None)

    return True

# ================= DATA =================
DATA = {
    "Arduino": {
        "text": """🔵 Arduino haqida:

Arduino — ochiq manbali mikrokontroller platformasi.

📌 ATmega328P chip
📌 14 digital pin
📌 6 analog pin
📌 5V ishlash kuchlanishi

Robototexnika va IoT loyihalarda ishlatiladi.""",
        "image": "arduino.png",
    },
    "DHT11": {"text": "🟢 DHT11 harorat va namlik sensori.\nVCC→5V\nGND→GND\nDATA→D2", "image": "dht11.jpg"},
    "DHT22": {"text": "🟢 DHT22 aniqligi yuqori sensor.\nVCC→5V\nGND→GND\nDATA→D2", "image": "dht22.jpg"},
    "Servo": {"text": "🟢 Servo motor.\nQizil→5V\nJigarrang→GND\nSariq→D9", "image": "servo.jpg"},
    "Stepper": {"text": "🟢 Stepper (ULN2003).\nIN1→D8\nIN2→D9\nIN3→D10\nIN4→D11", "image": "stepper.jpg"},
    "Bluetooth": {"text": "🟢 HC-05 Bluetooth.\nVCC→5V\nGND→GND\nTX→RX\nRX→TX", "image": "bluetooth.jpg"},
    "ESP32": {"text": """🔵 ESP32 haqida:

WiFi + Bluetooth chip
240MHz dual-core
3.3V logika
Ko‘plab GPIO pinlar""", "image": "esp32.jpg"},
    "RFID": {"text": "🟢 RFID RC522.\nSDA→D10\nSCK→D13\nMOSI→D11\nMISO→D12\nRST→D9", "image": "rfid.png"},
    "IR control": {"text": "🟢 IR Receiver.\nVCC→5V\nGND→GND\nOUT→D2", "image": "ir_control.jpg"},
    "LED": {"text": "🟢 LED ulanishi.\nAnod→220Ω→D13\nKatod→GND", "image": "led.jpg"},
}

# ================= MENU =================
def build_keyboard(button_names: list[str], include_back: bool = False) -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton(text=name, callback_data=name)] for name in button_names]
    if include_back:
        keyboard.append([InlineKeyboardButton(text=BACK_BUTTON, callback_data=BACK_BUTTON)])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def main_menu() -> InlineKeyboardMarkup:
    return build_keyboard(list(DATA.keys()))

# ================= HANDLERS =================
async def start(message: types.Message):
    user_id = message.from_user.id

    async def logic():
        text = message.text or ""
        if text.strip().lower() == "/start":
            await message.answer(
                'Botni ishga tushirish uchun pastdagi "Boshlash 🚀" tugmasini bosing.',
                reply_markup=ReplyKeyboardMarkup(
                    keyboard=[[KeyboardButton(text="Boshlash 🚀")]],  # keyword argument
                    resize_keyboard=True,
                    one_time_keyboard=True,
                ),
            )
            return

        # ReplyKeyboard tugmasi bosilganda
        await message.answer("📚 Modulni tanlang:", reply_markup=main_menu())
        await message.answer("Tugmalar olib tashlandi.", reply_markup=ReplyKeyboardRemove())

    result = await run_protected(user_id, logic)
    if result is False:
        await message.answer("Juda ko‘p so‘rov yubordingiz ❌")

async def callback_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data
    await callback.answer()

    async def logic():
        if data == BACK_BUTTON:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer("📚 Modulni tanlang:", reply_markup=main_menu())
            return

        module = DATA.get(data)
        if not module:
            await callback.message.answer(
                "Kutilmagan xato. Iltimos, /start yoki boshlash tugmasini bosing.",
                reply_markup=main_menu(),
            )
            return

        try:
            await callback.message.delete()
        except Exception:
            pass

        image_path = os.path.join(IMAGE_DIR, module["image"])
        if os.path.isfile(image_path):
            await callback.message.answer_photo(
                photo=FSInputFile(image_path),  # <-- FSInputFile bilan
                caption=module["text"],
                reply_markup=build_keyboard([], include_back=True),
            )
        else:
            await callback.message.answer(
                module["text"], reply_markup=build_keyboard([], include_back=True)
            )

    result = await run_protected(user_id, logic)
    if result is False:
        await callback.message.answer("Juda ko‘p bosdingiz ❌ Barcha so‘rovlar bekor qilindi.")

# ================= MAIN =================
async def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN muhit o'zgaruvchisi o'rnatilmagan")

    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    # Handlers registration
    dp.message.register(start, Command(commands=["start"]))
    # Lambda filter bilan text tekshirish
    dp.message.register(start, lambda m: m.text and m.text.lower() == "boshlash 🚀")
    dp.callback_query.register(callback_handler)

    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())