import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from PIL import Image, ImageDraw, ImageFont

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

class MemeStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_top_text = State()
    waiting_for_bottom_text = State()

@dp.message(Command("impact"))
async def start_cmd(message: Message, state: FSMContext):
    await message.answer("Скиньте кошерное изображение")
    await state.set_state(MemeStates.waiting_for_photo)

@dp.message(MemeStates.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    await state.update_data(photo_id=photo.file_id)
    await message.answer("Текст сверху: (-)")
    await state.set_state(MemeStates.waiting_for_top_text)

@dp.message(MemeStates.waiting_for_top_text)
async def process_top_text(message: Message, state: FSMContext):
    await state.update_data(top_text=message.text.upper())
    await message.answer("Текст снизу (-)")
    await state.set_state(MemeStates.waiting_for_bottom_text)

def wrap_text(text, font, max_width, draw):
    """Розбиває текст на кілька рядків, якщо він надто довгий"""
    if text == "-":
        return []
    
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        width = bbox[2] - bbox[0]
        
        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
            
    if current_line:
        lines.append(' '.join(current_line))
        
    return lines

def draw_meme_text(draw, text, is_top, image_width, image_height):
    if text == "-":
        return

    # 1. Початковий підбір розміру шрифту (базовий - 9% від ширини картинки)
    font_size = int(image_width * 0.09)
    max_text_width = int(image_width * 0.9) # 5% відступи по боках
    
    # Завантажуємо шрифт impact.ttf з папки проєкту
    font_path = "impact.ttf"
    if not os.path.exists(font_path):
        font_path = "LiberationSans-Bold.ttf" # Запасний, якщо забув залити
        
    try:
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()

    # 2. Динамічно зменшуємо шрифт, якщо текст гігантський, поки він не влізе хоча б у 3 рядки
    lines = wrap_text(text, font, max_text_width, draw)
    while len(lines) > 3 and font_size > 15:
        font_size -= 4
        try:
            font = ImageFont.truetype(font_path, font_size)
        except:
            break
        lines = wrap_text(text, font, max_text_width, draw)

    if not lines:
        return

    # Вираховуємо висоту одного рядка
    sample_bbox = draw.textbbox((0, 0), "AG", font=font)
    line_height = sample_bbox[3] - sample_bbox[1]
    
    # 3. Вираховуємо стартову позицію Y (верх чи низ)
    if is_top:
        y_pos = int(image_height * 0.04)
    else:
        # Для низу зміщуємо вгору на кількість рядків
        total_height = len(lines) * (line_height + 5)
        y_pos = int(image_height * 0.93) - total_height

    # 4. Малюємо кожен рядок з акуратною обводкою
    # Товщина контуру тепер залежить від розміру шрифту (робимо тоншим)
    outline_thickness = max(1, int(font_size * 0.05)) 

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        x_pos = (image_width - line_width) / 2
        
        # Малюємо оптимізовану обводку
        for adj_x in range(-outline_thickness, outline_thickness + 1):
            for adj_y in range(-outline_thickness, outline_thickness + 1):
                # Пропускаємо кути для м'якшого скруглення контуру
                if abs(adj_x) == outline_thickness and abs(adj_y) == outline_thickness:
                    continue
                draw.text((x_pos + adj_x, y_pos + adj_y), line, font=font, fill="black")
                
        # Основний текст
        draw.text((x_pos, y_pos), line, font=font, fill="white")
        y_pos += line_height + 5 # Крок на наступний рядок

@dp.message(MemeStates.waiting_for_bottom_text)
async def process_bottom_text(message: Message, state: FSMContext):
    user_data = await state.get_data()
    bottom_text = message.text.upper()
    top_text = user_data['top_text']
    
    await message.answer("Обробляю шрифт та переноси... Зачекай секунду.")
    
    file = await bot.get_file(user_data['photo_id'])
    file_bytes = await bot.download_file(file.file_path)
    
    with Image.open(file_bytes) as img:
        img = img.convert("RGB")
        width, height = img.size
        draw = ImageDraw.Draw(img)
        
        # Малюємо верхній текст
        draw_meme_text(draw, top_text, True, width, height)
        # Малюємо нижній текст
        draw_meme_text(draw, bottom_text, False, width, height)
        
        from io import BytesIO
        output_buffer = BytesIO()
        img.save(output_buffer, format="JPEG", quality=95)
        output_buffer.seek(0)
        
    input_file = BufferedInputFile(output_buffer.getvalue(), filename="meme.jpg")
    await message.answer_photo(photo=input_file)
    await state.clear()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
