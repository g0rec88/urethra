import os
import re
import random
import asyncio
from io import BytesIO
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from PIL import Image, ImageDraw, ImageFont
from aiohttp import web

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- СТАНИ FSM ---
class MemeStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_top_text = State()
    waiting_for_bottom_text = State()

class TextProcessingStates(StatesGroup):
    waiting_for_leet = State()
    waiting_for_niche = State()


# --- ТАБЛИЦІ ЗАМІН ТА ЛОГІКА ТЕКСТУ ---

# 1. Словник для /leetshi та Leet-стилю
LEET_MAP = {
    'а': '4', 'б': '6', 'в': 'B', 'г': 'r', 'д': 'D', 'е': '3', 'є': '3', 'ё': '3',
    'ж': '>|<', 'з': '3', 'и': 'U', 'і': 'I', 'ї': 'Yi', 'й': 'Y', 'к': 'K',
    'л': 'Jl', 'м': 'M', 'н': 'H', 'о': '0', 'п': 'n', 'р': 'P', 'с': 'C',
    'т': 'T', 'у': 'Y', 'ф': 'F', 'х': 'X', 'ц': 'C', 'ч': '4', 'ш': 'W',
    'щ': 'W', 'ъ': "'", 'ы': 'bl', 'ь': 'b', 'э': '3', 'ю': '10', 'я': 'R'
}

# 2. Словник для англійських/трансліт аналогів у "нішовому" стилі
TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'є': 'ye',
    'ж': 'zh', 'з': 'z', 'и': 'y', 'і': 'i', 'ї': 'yi', 'й': 'y', 'к': 'k',
    'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 'c',
    'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh',
    'щ': 'sch', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
}


def convert_to_leet(text: str) -> str:
    """Повний 1337-переклад без урахування регістру."""
    return ''.join(LEET_MAP.get(char.lower(), char) for char in text)


def convert_to_niche(text: str) -> str:
    """Читабельний нішовий стиль з міксом leet/англ по словах, помірною заміною та випадковим CAPS."""
    tokens = re.split(r'(\s+|[.,!?]+)', text)
    result = []

    for token in tokens:
        if not token:
            continue

        # Обробка пробілів (~7% шанс видалення)
        if re.match(r'^\s+$', token):
            if random.random() < 0.07:
                continue
            result.append(token)
            continue

        # Обробка пунктуації (~20% шанс дублювання розділових знаків)
        if re.match(r'^[.,!?]+$', token):
            if random.random() < 0.20:
                token = token * random.randint(2, 3)
            result.append(token)
            continue

        word = token

        # ~15% шанс перевести окреме слово у CAPS
        is_caps = random.random() < 0.15
        if is_caps:
            word = word.upper()

        # Для конкретного слова вибираємо єдиний стиль (Leet або Translit)
        use_leet = random.choice([True, False])
        current_map = LEET_MAP if use_leet else TRANSLIT_MAP

        new_word = []
        for char in word:
            char_lower = char.lower()
            
            # Заміняємо ~35% літер у слові для збереження читабельності
            if char_lower in current_map and random.random() < 0.35:
                replacement = current_map[char_lower]
                if is_caps and len(replacement) == 1:
                    replacement = replacement.upper()
                new_word.append(replacement)
            else:
                new_word.append(char)

        result.append(''.join(new_word))

    return ''.join(result)


# --- ВЕБСЕРВЕР ДЛЯ РЕНДЕРУ ---
async def handle_ping(request):
    return web.Response(text="Bot is running!", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


# --- ОБРОБНИКИ КОМАНД /leetshi ТА /nichetxt ---

@dp.message(Command("leetshi"))
async def leetshi_cmd(message: Message, state: FSMContext):
    await message.answer("Таки отправьте текст:")
    await state.set_state(TextProcessingStates.waiting_for_leet)

@dp.message(TextProcessingStates.waiting_for_leet, F.text)
async def process_leet_text(message: Message, state: FSMContext):
    converted = convert_to_leet(message.text)
    await message.answer(converted)
    await state.clear()


@dp.message(Command("nichetxt"))
async def nichetxt_cmd(message: Message, state: FSMContext):
    await message.answer("Таки отправьте текст:")
    await state.set_state(TextProcessingStates.waiting_for_niche)

@dp.message(TextProcessingStates.waiting_for_niche, F.text)
async def process_niche_text(message: Message, state: FSMContext):
    converted = convert_to_niche(message.text)
    await message.answer(converted)
    await state.clear()


# --- ОБРОБНИКИ КОМАНДИ /impact (МЕМИ) ---

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

@dp.message(MemeStates.waiting_for_top_text, F.text)
async def process_top_text(message: Message, state: FSMContext):
    await state.update_data(top_text=message.text.upper())
    await message.answer("Текст снизу (-)")
    await state.set_state(MemeStates.waiting_for_bottom_text)

def wrap_text(text, font, max_width, draw):
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

    paragraphs = text.split('\n')
    all_lines = []
    for para in paragraphs:
        if para.strip():
            para_lines = wrap_text(para, font, max_text_width, draw)
            all_lines.append((para_lines, True))
        else:
            all_lines.append(([""], False))

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
    line_spacing = int(line_height * 0.25)
    paragraph_spacing = int(line_height * 0.65)
    
    total_text_height = 0
    for i, (lines, is_para_end) in enumerate(all_lines):
        total_text_height += len(lines) * line_height + (len(lines) - 1) * line_spacing
        if i < len(all_lines) - 1 and is_para_end:
            total_text_height += paragraph_spacing

    if is_top:
        y_pos = int(image_height * 0.04)
    else:
        y_pos = int(image_height * 0.94) - total_text_height

    outline_thickness = max(1, int(font_size * 0.05))

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

@dp.message(MemeStates.waiting_for_bottom_text, F.text)
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
        
        draw_meme_text(draw, top_text, True, width, height)
        draw_meme_text(draw, bottom_text, False, width, height)
        
        output_buffer = BytesIO()
        img.save(output_buffer, format="JPEG", quality=95)
        output_buffer.seek(0)
        
    input_file = BufferedInputFile(output_buffer.getvalue(), filename="meme.jpg")
    await message.answer_photo(photo=input_file)
    await state.clear()


async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
