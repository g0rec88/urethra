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
    font_size = int(image_width * 0.09)
    max_text_width = int(image_width * 0.9)
    font_path = "impact.ttf"
    if not os.path.exists(font_path):
        font_path = "LiberationSans-Bold.ttf"
    try:
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()

    # Розбиваємо текст на абзаци, які ввів користувач (через Shift+Enter / Enter)
    paragraphs = text.split('\n')
    all_lines = []
    
    # Для кожного абзацу робимо переноси слів
    for para in paragraphs:
        if para.strip():
            para_lines = wrap_text(para, font, max_text_width, draw)
            all_lines.append((para_lines, True)) # True означає кінець абзацу
        else:
            all_lines.append(([""], False))

    # Динамічно зменшуємо шрифт, якщо тексту забагато
    total_lines_count = sum(len(p[0]) for p in all_lines)
    while total_lines_count > 4 and font_size > 15:
        font_size -= 4
        try:
            font = ImageFont.truetype(font_path, font_size)
        except:
            break
        all_lines = []
        for para in paragraphs:
            if para.strip():
                all_lines.append((wrap_text(para, font, max_text_width, draw), True))
            else:
                all_lines.append(([""], False))
        total_lines_count = sum(len(p[0]) for p in all_lines)

    sample_bbox = draw.textbbox((0, 0), "AG", font=font)
    line_height = sample_bbox[3] - sample_bbox[1]
    
    # Регулюємо відступи: між рядками 25% від висоти шрифту, між абзацами — 65%
    line_spacing = int(line_height * 0.25)
    paragraph_spacing = int(line_height * 0.65)
    
    # Рахуємо повну висоту всього тексту з урахуванням нових відступів
    total_text_height = 0
    for i, (lines, is_para_end) in enumerate(all_lines):
        total_text_height += len(lines) * line_height + (len(lines) - 1) * line_spacing
        if i < len(all_lines) - 1 and is_para_end:
            total_text_height += paragraph_spacing

    # Визначаємо стартову позицію Y
    if is_top:
        y_pos = int(image_height * 0.04)
    else:
        y_pos = int(image_height * 0.94) - total_text_height

    outline_thickness = max(1, int(font_size * 0.05))

    # Малюємо текст
    for lines, is_para_end in all_lines:
        for i, line in enumerate(lines):
            if not line:
                continue
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            x_pos = (image_width - line_width) / 2
            
            for adj_x in range(-outline_thickness, outline_thickness + 1):
                for adj_y in range(-outline_thickness, outline_thickness + 1):
                    if abs(adj_x) == outline_thickness and abs(adj_y) == outline_thickness:
                        continue
                    draw.text((x_pos + adj_x, y_pos + adj_y), line, font=font, fill="black")
            
            draw.text((x_pos, y_pos), line, font=font, fill="white")
            y_pos += line_height + line_spacing
            
        if is_para_end:
            y_pos += paragraph_spacing - line_spacing

@dp.message(MemeStates.waiting_for_bottom_text)
async def process_bottom_text(message: Message, state: FSMContext):
    user_data = await state.get_data()
    bottom_text = message.text.upper()
    top_text = user_data['top_text']
    
    await message.answer("Лее брат падажжи секунд.")
    
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
