import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from PIL import Image, ImageDraw, ImageFont

# Токен вставляємо з екологічних міркувань через змінні оточення на Render
TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Стейт-машина для покрокового опитування
class MemeStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_top_text = State()
    waiting_for_bottom_text = State()

@dp.message(Command("start", "makememe"))
async def start_cmd(message: Message, state: FSMContext):
    await message.answer("Привіт! Скинь мені картинку, з якої хочеш зробити мем.")
    await state.set_state(MemeStates.waiting_for_photo)

@dp.message(MemeStates.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    # Беремо найбільшу якість фото
    photo = message.photo[-1]
    await state.update_data(photo_id=photo.file_id)
    await message.answer("Тепер напиши ТЕКСТ ДЛЯ ВЕРХУ (якщо не треба, напиши мінус: - )")
    await state.set_state(MemeStates.waiting_for_top_text)

@dp.message(MemeStates.waiting_for_top_text)
async def process_top_text(message: Message, state: FSMContext):
    await state.update_data(top_text=message.text.upper())
    await message.answer("І останнє: напиши ТЕКСТ ДЛЯ НИЗУ (якщо не треба, напиши мінус: - )")
    await state.set_state(MemeStates.waiting_for_bottom_text)

def draw_meme_text(draw, text, y_pos, image_width, font):
    if text == "-":
        return
    
    # Вираховуємо розмір тексту для центрування
    text_box = draw.textbbox((0, 0), text, font=font)
    text_width = text_box[2] - text_box[0]
    x_pos = (image_width - text_width) / 2
    
    # Малюємо чорний контур (обводку) в 4 сторони
    outline_range = 3
    for adj_x in range(-outline_range, outline_range + 1):
        for adj_y in range(-outline_range, outline_range + 1):
            draw.text((x_pos + adj_x, y_pos + adj_y), text, font=font, fill="black")
            
    # Малюємо основний білий текст поверх контуру
    draw.text((x_pos, y_pos), text, font=font, fill="white")

@dp.message(MemeStates.waiting_for_bottom_text)
async def process_bottom_text(message: Message, state: FSMContext):
    user_data = await state.get_data()
    bottom_text = message.text.upper()
    top_text = user_data['top_text']
    
    await message.answer("Генерую мем, зачекай секунду...")
    
    # Завантажуємо фото з серверів Telegram у пам'ять
    file = await bot.get_file(user_data['photo_id'])
    file_bytes = await bot.download_file(file.file_path)
    
    # Обробка картинки через Pillow
    with Image.open(file_bytes) as img:
        img = img.convert("RGB")
        width, height = img.size
        draw = ImageDraw.Draw(img)
        
        # Динамічний розмір шрифту залежно від ширини картинки
        font_size = int(width * 0.08)
        try:
            # На Render зазвичай є стандартні лінуксові шрифти
            font = ImageFont.truetype("LiberationSans-Bold.ttf", font_size)
        except:
            font = ImageFont.load_default()
            
        # Малюємо верхній текст (відступ 5% від верху)
        draw_meme_text(draw, top_text, int(height * 0.05), width, font)
        # Малюємо нижній текст (відступ 15% від низу, щоб помістився розмір літер)
        draw_meme_text(draw, bottom_text, int(height * 0.82), width, font)
        
        # Зберігаємо результат у байтовий буфер, щоб відправити без збереження файлу на диск
        from io import BytesIO
        output_buffer = BytesIO()
        img.save(output_buffer, format="JPEG", quality=90)
        output_buffer.seek(0)
        
    # Відправляємо готовий мем користувачу
    input_file = BufferedInputFile(output_buffer.getvalue(), filename="meme.jpg")
    await message.answer_photo(photo=input_file)
    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())